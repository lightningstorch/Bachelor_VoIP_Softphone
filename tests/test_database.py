import pytest
from unittest.mock import patch
import datetime

from datastructure.database.database import (
    init_db, get_engine, store_call_start, store_call_end,
    store_ssrc, store_talking_sections, get_call_by_id, get_call_history_lite,
    get_call_for_api, get_program_mode, set_program_mode, get_user,
    set_user, change_password, remove_user
)
from datastructure.database.models import Base
from datastructure.dataclass_models import CallInfo, TalkingInterval, ParticipantInfo

#===============================================
#               Pytest Fixtures
#===============================================

@pytest.fixture(autouse=True)
def setup_db():
    """Setup in-memory database for testing."""
    # Mock the config values
    with patch('datastructure.database.database._engine', None), \
            patch('datastructure.database.database._session', None), \
            patch('config.config.database_connection', 'sqlite:///:memory:'), \
            patch('config.config.database_type', 'sqlite'):
        # Get a fresh engine and create tables
        engine = get_engine()
        Base.metadata.create_all(engine)

        yield

        # Clean up after test
        Base.metadata.drop_all(engine)

@pytest.fixture
def sample_call_info():
    """Create a sample CallInfo object."""
    return CallInfo(
        caller="test_caller",
        start_time=datetime.datetime.now(),
        participants=[
            ParticipantInfo(
                user="test_user_1",
                ip_address="10.0.0.0",
                media_port=1234,
                mime_type="opus",
                server_ip="192.168.0.0",
                server_port=5678,
            ),
            ParticipantInfo(
                user="test_user_2",
                ip_address="172.168.0.0",
                media_port=4321,
                mime_type="opus",
                server_ip="192.168.10.10",
                server_port=8765,
            )
        ],
        ack_received=True,
        stored=True
    )

#===============================================
#               Test Cases
#===============================================

class TestDatabase:
    def test_init_db(self):
        """Test database initialization."""
        init_db()

    def test_store_and_get_call(self, sample_call_info):
        """Test storing and retrieving a call."""
        call_id = "test_call_id"
        store_call_start(call_id, sample_call_info)

        call = get_call_by_id(call_id)

        assert call is not None
        assert call.id == call_id
        assert call.caller == sample_call_info.caller
        assert call.start_time == sample_call_info.start_time
        assert call.end_time is None
        assert len(call.participants) == len(sample_call_info.participants)
        for i, participant in enumerate(call.participants):
            assert participant.user == sample_call_info.participants[i].user
            assert participant.ip_address == sample_call_info.participants[i].ip_address
            assert participant.media_port == sample_call_info.participants[i].media_port
            assert participant.mime_type == sample_call_info.participants[i].mime_type
            assert participant.server_ip == sample_call_info.participants[i].server_ip
            assert participant.server_port == sample_call_info.participants[i].server_port

    def test_store_call_start_update(self, sample_call_info):
        """Test storing a call with start time and updating it."""
        call_id = "test_call_start_update"
        store_call_start(call_id, sample_call_info)

        # Update the call with new start time
        new_start_time = datetime.datetime.now() + datetime.timedelta(seconds=10)
        sample_call_info.start_time = new_start_time
        store_call_start(call_id, sample_call_info)

        call = get_call_by_id(call_id)

        assert call is not None
        assert call.id == call_id
        assert call.start_time == new_start_time
        assert len(call.participants) == len(sample_call_info.participants)

    def test_store_call_start_twice_same(self, sample_call_info):
        """Test storing the same call start twice."""
        call_id = "test_call_start_twice_same"
        store_call_start(call_id, sample_call_info)

        # Store the same call again
        result = store_call_start(call_id, sample_call_info)

        assert result is False # Should return False since the call already exists

    def test_store_call_end(self, sample_call_info):
        """Test storing the end time of a call."""
        call_id = "test_call_end"
        store_call_start(call_id, sample_call_info)

        end_time = datetime.datetime.now()
        sample_call_info.end_time = end_time
        store_call_end(call_id, sample_call_info)

        call = get_call_by_id(call_id)

        assert call is not None
        assert call.id == call_id
        assert call.end_time == end_time

    def test_store_call_end_without_store_call(self, sample_call_info):
        """Test storing end time without storing call start."""
        call_id = "test_call_end_without_start"
        end_time = datetime.datetime.now()
        sample_call_info.end_time = end_time

        result = store_call_end(call_id, sample_call_info)

        assert result is False  # Should return False since call was not started

    def test_store_ssrc(self, sample_call_info):
        """Test storing SSRC for participants in a call."""
        call_id = "test_store_ssrc"
        store_call_start(call_id, sample_call_info)

        new_ssrc_1 = "new_ssrc_1"
        new_ssrc_2 = "new_ssrc_2"

        store_ssrc(call_id, new_ssrc_1, sample_call_info.participants[0].user)
        store_ssrc(call_id, new_ssrc_2, sample_call_info.participants[1].user)

        call = get_call_by_id(call_id)
        assert call is not None
        assert len(call.participants) == len(sample_call_info.participants)

        assert call.participants[0].ssrc == new_ssrc_1
        assert call.participants[1].ssrc == new_ssrc_2

    def test_store_ssrc_without_call(self, sample_call_info):
        """Test storing SSRC without a call."""
        call_id = "test_store_ssrc_without_call"
        new_ssrc = "new_ssrc"

        result = store_ssrc(call_id, new_ssrc, sample_call_info.participants[0].user)

        assert result is False # Should return False since call does not exist

    def test_store_talking_sections(self, sample_call_info):
        """Test storing talking sections in a call."""
        call_id = "test_store_talking_sections"
        store_call_start(call_id, sample_call_info)

        new_ssrc_1 = "new_ssrc_1"
        new_ssrc_2 = "new_ssrc_2"

        talking_section_1 = TalkingInterval(
            type="speech",
            call_id=call_id,
            ssrc=new_ssrc_1,
            start=0.0,
            end=5.0
        )
        talking_section_2 = TalkingInterval(
            type="overlapping",
            call_id=call_id,
            ssrc=new_ssrc_2,
            start=3.0,
            end=7.0
        )

        store_talking_sections(talking_section_1)
        store_talking_sections(talking_section_2)

        call = get_call_by_id(call_id)
        assert call is not None
        assert len(call.talking_sections) == 2

        speech_sections = [s for s in call.talking_sections if s.type == "speech"]
        overlap_sections = [s for s in call.talking_sections if s.type == "overlapping"]

        assert len(speech_sections) == 1
        assert len(overlap_sections) == 1

        assert speech_sections[0].section_start == 0.0
        assert speech_sections[0].section_end == 5.0

        assert overlap_sections[0].section_start == 3.0
        assert overlap_sections[0].section_end == 7.0

    def test_user_operations(self):
        """Test user operations like getting, setting, changing password, and removing user."""
        # Set a user
        username = "test_user"
        password = "test_password"
        set_user(username, password)

        # Get user
        user = get_user(username)
        assert user is not None
        assert user.username == username

        # Change password
        new_password = "new_password"
        change_password(username, new_password)
        user = get_user(username)
        assert user.password == new_password

        # Remove user
        remove_user(username)
        user = get_user(username)
        assert user is None

    def test_program_mode(self):
        """Test getting and setting program mode."""
        # Set program mode
        mode = "test_mode"
        set_program_mode(mode)

        # Get program mode
        program_mode = get_program_mode()
        assert program_mode is not None
        assert program_mode == mode

        # Change program mode
        new_mode = "new_test_mode"
        set_program_mode(new_mode)
        program_mode = get_program_mode()
        assert program_mode == new_mode

    def test_get_call_history_lite(self, sample_call_info):
        """Test getting call history in lite format."""
        call_id = "test_call_history_lite"
        store_call_start(call_id, sample_call_info)

        history = get_call_history_lite()
        assert len(history) > 0
        assert history[0].call_id == call_id
        assert history[0].caller == sample_call_info.caller
        assert history[0].start_time == sample_call_info.start_time.isoformat()

    def test_get_call_for_api(self, sample_call_info):
        """Test getting call details for API."""
        call_id = "test_call_for_api"
        store_call_start(call_id, sample_call_info)

        call_detail = get_call_for_api(call_id)
        assert call_detail is not None
        assert call_detail.call_id == call_id
        assert call_detail.caller == sample_call_info.caller
        assert call_detail.start_time == sample_call_info.start_time.isoformat()
        assert len(call_detail.participants) == len(sample_call_info.participants)

        # Check participants
        for i, participant in enumerate(call_detail.participants):
            assert participant.user == sample_call_info.participants[i].user
            assert participant.ip_address == sample_call_info.participants[i].ip_address
            assert participant.media_port == sample_call_info.participants[i].media_port
            assert participant.mime_type == sample_call_info.participants[i].mime_type
            assert participant.server_ip == sample_call_info.participants[i].server_ip
            assert participant.server_port == sample_call_info.participants[i].server_port











