
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
from enum import Enum

class EventType(Enum):
    NEW_CALL = "NEW_CALL"
    RTP_PAKET = "RTP_PAKET"
    LOG = "LOG"


@dataclass
class Event: # TODO include every Element that is possible in a event
    type: EventType
    call_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

