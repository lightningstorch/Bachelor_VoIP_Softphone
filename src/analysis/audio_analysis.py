import av
import numpy as np
import webrtcvad

from typing import Any
from scipy.signal import butter, sosfilt
from config.config import bandpass_min_frequency, bandpass_max_frequency, bandpass_order, audio_min_speech_duration, \
    audio_gap_threshold, audio_allowed_gaps, vad_mode, noise_multiplier, noise_percentile, default_audio_sample_rate
from my_logging.log_config import call_context_logger

# Semantic Versioning for AudioAnalysis (MAJOR.MINOR.PATCH):
#   MAJOR version when you make incompatible API changes or large new features
#   MINOR version when you add functionality in a backwards-compatible manner or make medium enhancements
#   PATCH version when you make backwards-compatible bug fixes or minor tweaks
__version__ = "1.1.2"

class AudioAnalysis:
    """
    Processes Opus audio packets, detects speech segments, and applies bandpass filtering.

    Utilizes WebRTC VAD (Voice Activity Detection) together with RMS (Root Mean Square)
    analysis to identify speech intervals in mono PCM audio.

    Features:
    - Opus decoding & resampling (PyAV)
    - Bandpass filtering (SciPy) within a configurable frequency range
    - Speech detection based on RMS thresholds and VAD output
    - Gap detection and merging of short pauses between speech segments
    - Filtering of segments by minimum duration

    Dependencies:
        av, webrtcvad, numpy, scipy
    """

    def __init__(self, ssrc: str, sample_rate: int):
        self.ssrc = ssrc

        # Audio parameters (from client)
        self.sample_rate = sample_rate

        # Initialize the decoder for Opus audio
        self.codec: Any = av.CodecContext.create("opus", "r")
        self.codec.sample_rate = self.sample_rate

        # the rtp payload has 2 channels but VAD can only use 1 channel
        self.resampler = av.AudioResampler(
            format='s16',
            layout='mono',
            rate=self.sample_rate
        )

        # WebRTC VAD setup
        self.vad = webrtcvad.Vad(vad_mode)
        self.frame_duration_ms = 20
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000.0)

        # Initialize RMS values and noise threshold
        self._rms_values_initial: list[float] = []
        self._noise_threshold: float | None = None
        self._collect_rms_for = 50
        self.frequency_filtering = None

        # filtering the segments to a minimum duration
        self._min_speech_duration = audio_min_speech_duration

        # Initialize variables for speech detection
        self.first_timestamp = None
        self._current_speech_start = None
        self._last_section_end_ts = None

        # Buffer for pending bytes that did not fit into a complete frame
        self._pending_bytes = b''

        # Thresholds for gap detection
        self.gap_threshold_s = audio_gap_threshold
        self.allowed_gap_s = audio_allowed_gaps

        # List to store all intervals found during analysis
        self.all_intervals: list[tuple[float, float]] = []
        self._last_returned_end_time : float = 0.0

        # Last delta timestamp for the current packet
        self._last_delta_ts : float | None = None

        # bandpass filtering values
        self.bandpass_min_f = bandpass_min_frequency
        self.bandpass_max_f = bandpass_max_frequency
        self.bandpass_order = bandpass_order

        # noise reduction parameters
        self.noise_multiplier = noise_multiplier
        self.noise_percentile = noise_percentile

    def analyze_audio(self, packet) -> list[tuple[float, float]]:

        packets_sorted = sorted(packet, key=lambda p: p.sniff_timestamp)

        for pkt in packets_sorted:

            if len(pkt.rtp.payload.binary_value) < 12:
                continue

            rtp_timestamp = int(pkt.rtp.timestamp)

            if self.first_timestamp is None:
                self.first_timestamp = rtp_timestamp

            delta_ts = (rtp_timestamp - self.first_timestamp) / self.sample_rate

            # Check if there is a gabe between Packet and Packet before
            interval = self._gap_check(delta_ts)
            if interval:
                self.all_intervals.extend(interval)

            # Process the Opus payload
            self._process_opus_payload(pkt.rtp.payload.binary_value, delta_ts)

        merged = self._merge_short_gaps(sorted(self.all_intervals, key=lambda x: x[0]))

        # remove the last segment if it is still in progress -> the segment is not complete
        if self._current_speech_start is not None and merged:
            merged.pop()

        result = self._filter_min_duration(merged)

        # save the last interval (end time) to avoid returning the same segment again
        if result:
            self._last_returned_end_time = result[-1][1]

        return result

    def _process_opus_payload(self, opus_payload, delta_ts):
        self._last_delta_ts = delta_ts

        if not (pcm_accumulator := self._decode_opus_payload(opus_payload)):
            return

        # calculate the 20 ms block (960 Samples)
        block_bytes = self.frame_size * 2
        total_len = len(pcm_accumulator)
        num_full = total_len // block_bytes
        end_full = num_full * block_bytes

        blocks = self._calc_blocks(pcm_accumulator)

        if self._noise_threshold is None:
            if not self._init_noise_threshold(blocks):
                # not enough data to calculate the noise threshold
                self._pending_bytes = pcm_accumulator[end_full:]
                return

        # VAD analysis
        self._analyse_blocks(blocks, delta_ts)

        # If there are no full blocks, we store the remaining bytes for the next call
        if end_full < total_len:
            self._pending_bytes = bytes(pcm_accumulator[end_full:])
        else:
            self._pending_bytes = b''

    def _decode_opus_payload(self, opus_payload: bytes) -> bytes | None:
        """
        Decodes the Opus payload into PCM audio data.
        :param opus_payload: the Opus payload as bytes
        :return: the PCM audio data as bytes, or None if decoding fails
        """
        # convert the opal_payload into an AVPacket
        try:
            frames = self.codec.decode(av.Packet(opus_payload))
        except Exception as e:
            call_context_logger.error(f"Error by decoding Opus payload for {self.ssrc}: {e}")
            return None


        pcm = bytearray()
        # Iterate through the frames and resample them to mono PCM
        for frame in frames:
            for out_frame in self.resampler.resample(frame):
                pcm.extend(bytes(out_frame.planes[0]))

        if self._pending_bytes:
            pcm = bytearray(self._pending_bytes) + pcm

        return bytes(pcm)

    def _calc_blocks(self, pcm: bytes) -> list[bytes]:
        """
        Splits the PCM data into blocks of 20 ms (960 samples) for further processing.

        :param pcm: the PCM audio data as bytes
        :return: a list of byte blocks, each representing 20 ms of audio
        """
        block_size = self.frame_size * 2
        full_blocks = len(pcm) // block_size
        return [pcm[i*block_size : (i + 1) * block_size] for i in range(full_blocks)]

    def _analyse_blocks(self, blocks: list[bytes], delta_ts: float):
        """
        Analyzes the audio blocks to detect speech segments using VAD and RMS thresholding.
        This method processes each block, applies a bandpass filter, calculates the RMS,
        and uses the VAD to determine if the block contains speech.
        :param blocks: the list of audio blocks to analyze
        :param delta_ts: the delta timestamp of the current packet
        """
        for i, block in enumerate(blocks):
            samples = np.frombuffer(block, dtype=np.int16).astype(np.float32)
            filtered = self._bandpass_filter(samples)
            rms = float(np.sqrt(np.mean(filtered ** 2)))

            is_speech = False
            if rms >= self._noise_threshold:
                # the VAD will only be used if the RMS is above the noise threshold
                is_speech = self.vad.is_speech(block, sample_rate=self.sample_rate)

            frame_start = delta_ts + (i * self.frame_duration_ms / 1000.0)
            frame_end = frame_start + (self.frame_duration_ms / 1000.0)

            if is_speech:
                # If this is the start of a speech interval
                if self._current_speech_start is None:
                    self._current_speech_start = frame_start
                self._last_section_end_ts = frame_end

    def _init_noise_threshold(self, blocks: list[bytes]) -> None:
        """
        Initializes the noise threshold based on the first few blocks of audio.
        This is used to determine if a block is considered speech or not.

        :param blocks: the list of audio blocks to analyze
        """
        for block in blocks:
            samples = np.frombuffer(block, dtype=np.int16).astype(np.float32)
            block_rms = float(np.sqrt(np.mean(samples ** 2)))

            self._rms_values_initial.append(block_rms)
            if len(self._rms_values_initial) >= self._collect_rms_for:
                noise_floor = float(np.percentile(self._rms_values_initial, self.noise_percentile))
                self._noise_threshold = noise_floor * self.noise_multiplier
                break

    def close(self) -> list[tuple[float, float]] | None:
        """Return the final speech segment if one is in progress"""

        if self._current_speech_start is not None and self._last_section_end_ts is not None:
            final_interval = (round(self._current_speech_start, 2), round(self._last_section_end_ts, 2))

            # check if the interval is long enough (min_speech_segment)
            if (final_interval[1] - final_interval[0]) >= self._min_speech_duration:
                self.all_intervals.append(final_interval)
                self._last_returned_end_time = final_interval[1]
                return [final_interval]

        return None

    def _gap_check(self, delta_ts: float) -> list[tuple[float, float]] | None:
        """
        Checks if there is a gap between the current speech segment and the last section end.

        :param delta_ts: the delta timestamp of the current packet
        :return: the completed interval if there is a gap, otherwise None.
        """
        if self._current_speech_start is None or self._last_section_end_ts is None:
            return None

        if (delta_ts - self._last_section_end_ts) > self.gap_threshold_s:
            completed_interval = (round(self._current_speech_start, 2), round(self._last_section_end_ts, 2))
            self._current_speech_start = None
            self._last_section_end_ts = None
            return [completed_interval]

        return None

    def _bandpass_filter(self, samples: np.ndarray):
        """
        Applies a bandpass filter to the samples to remove frequencies outside the range of
        the range of 300 Hz - 3400 Hz.

        :param samples: the audio sample as numpy array
        :return: the samples after filtering
        """
        if self.frequency_filtering is None:
            sos = butter(
                self.bandpass_order,
                [self.bandpass_min_f, self.bandpass_max_f],
                btype='band',
                fs=self.sample_rate,
                output='sos'
            )
            self.frequency_filtering = sos
        else:
            sos = self.frequency_filtering
        return sosfilt(sos, samples)

    def _merge_short_gaps(self, intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """
        Merges intervals that are separated by a gap smaller than the allowed_gap_s.
        This is useful to combine short speech segments that are close together into a single segment.

        :param intervals: the list of intervals to merge
        :return: the merged intervals with the allowed gaps removed.
        """
        if not intervals:
            return []

        merged = []
        current_start, current_end = intervals[0]

        for (start, end) in intervals[1:]:
            if start - current_end <= self.allowed_gap_s:
                # gap is small enough ⇒ extend current_end
                current_end = max(current_end, end)
            else:
                # gap is too large ⇒ save the old interval and start a new one
                merged.append((current_start, current_end))
                current_start, current_end = start, end

        # add the last interval
        merged.append((current_start, current_end))
        return merged

    def _filter_min_duration(self, intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """
        Filters the intervals to only include those that are longer than the minimum speech segment duration.

        :param intervals: the list of intervals to filter
        :return: the filtered list of intervals
        """
        return [
            (start, end)
            for (start, end) in intervals
            if (end - start) >= self._min_speech_duration
            and end > self._last_returned_end_time
        ]
