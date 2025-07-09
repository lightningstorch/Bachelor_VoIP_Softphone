
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from enum import Enum
from pydantic import BaseModel


# -------------------------------------------------------------------
# Categories
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
    SERVER_INFO = "SERVER_INFO"
    TALKING_INTERVAL = "TALKING_INTERVAL"
    API = "API"

# -------------------------------------------------------------------
# Dataclass for the aggregator to store information in the dictionary
# -------------------------------------------------------------------
@dataclass
class ParticipantInfo:
    user: str
    ip_address: str = None
    media_port: int = None
    mime_type: str = None
    server_ip: str = None
    server_port: int = None
    ssrc: str = None

@dataclass
class CallInfo:
    caller: str = None
    start_time: datetime = None
    end_time: datetime = None
    participants: List[ParticipantInfo] = field(default_factory=list)
    ack_received: bool = False


# -------------------------------------------------------------
# Dataclass for the Message_Service to transfer the information
# -------------------------------------------------------------

class Call(BaseModel):
    type: EventType
    call_id: str
    caller: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class Participant(BaseModel):
    type: EventType
    call_id: str
    user: str
    ssrc: str | None = None
    ip_address: str
    media_port: int
    mime_type: str
    server_ip: str | None = None
    server_port: int | None = None

class Info(BaseModel):
    type: EventType
    call_id: str
    amount_participant: int
    participants: List[ParticipantInfo] = field(default_factory=list)

class ServerInfo(BaseModel):
    type: EventType
    call_id: str
    server_ip: str
    server_port: int
    user: str


class TalkingInterval(BaseModel):
    type: str # "speech" or "silence"
    call_id: str
    ssrc: str | None
    start: float
    end: float


# ----------------------
# Dataclass for the API
# ----------------------

class CallHistoryLite(BaseModel):
    call_id: str
    caller: str
    start_time: str

class CallDetail(BaseModel):
    call_id: str
    caller: str
    start_time: str
    end_time: str
    participants: List[Participant]
    talking_interval: List[TalkingInterval]



