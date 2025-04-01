
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
from enum import Enum

class EventType(Enum):
    NEW_CALL = "NEW_CALL"
    CALL_STARTED = "CALL_STARTED"
    CALL_END = "CALL_END"
    RTP_PAKET = "RTP_PAKET"
    LOG = "LOG"
    PARTICIPANTS = "PARTICIPANTS"


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
