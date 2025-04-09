
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


# -------------------------------------------------------------------
# Categories of events
# -------------------------------------------------------------------
class EventType(Enum):
    NEW_CALL = "NEW_CALL"
    ACK = "ACK"
    CALL_END = "CALL_END"
    RTP_PAKET = "RTP_PAKET"
    LOG = "LOG"
    PARTICIPANTS = "PARTICIPANTS"
    CALL_INIT = "CALL_INIT"
    CALL_DECLINE = "CALL_DECLINE"

# -------------------------------------------------------------------
# Dataclass for the aggregator to store information in the dictionary
# -------------------------------------------------------------------
@dataclass
class ParticipantInfo:
    user: str
    media_port: int
    mime_type: str = None

@dataclass
class CallInfo:
    start_time: datetime = None
    end_time: datetime = None
    participants: List[ParticipantInfo] = field(default_factory=list)


# ------------------------------------------------------
# Dataclass for the Eventbus to transfer the information
# ------------------------------------------------------
@dataclass
class Call:
    type: EventType
    call_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

@dataclass
class Participant:
    type: EventType
    call_id: str
    user: str
    media_port: int
    mime_type: str

@dataclass
class Info:
    type: EventType
    call_id: str
    amount_participant: int
    participants: List[ParticipantInfo] = field(default_factory=list)



