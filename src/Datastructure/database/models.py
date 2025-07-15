from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, UniqueConstraint, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Calls(Base):
    __tablename__ = 'calls'
    id = Column(String, primary_key=True)
    caller = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    # relationship to participants
    participants = relationship("Participants", back_populates="call")

    # relationship to talking_section
    talking_sections = relationship("TalkingSections", back_populates="call")


class Participants(Base):
    __tablename__ = 'participants'
    id = Column(Integer, primary_key=True)
    call_id = Column(String, ForeignKey('calls.id'), nullable=False)
    user = Column(String, nullable=False)
    ssrc = Column(String, nullable=True)
    ip_address = Column(String, nullable=False)
    media_port = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=True)
    server_ip = Column(String, nullable=False)
    server_port = Column(Integer, nullable=False)

    # relationship to calls
    call = relationship("Calls", back_populates="participants")

    # relationship to talking_section
    talking_sections = relationship("TalkingSections", back_populates="participant")


class TalkingSections(Base):
    __tablename__ = 'talking_sections'

    id = Column(Integer, primary_key=True)
    call_id = Column(String, ForeignKey('calls.id'), nullable=False)
    participant_id = Column(Integer, ForeignKey('participants.id'), nullable=True)
    type = Column(String, nullable=False)  # "speech" or "overlapping"
    section_start = Column(Float, nullable=False)
    section_end = Column(Float, nullable=False)

    participant = relationship("Participants", back_populates="talking_sections")
    call = relationship("Calls", back_populates="talking_sections")

    __table_args__ = (
        Index(
            'ux_talking_sections_full',
            'call_id',
            func.coalesce(participant_id, -1),
            'type',
            'section_start',
            'section_end',
            unique=True
        ),
    )


class ProgramMode(Base):
    __tablename__ = 'program_mode'
    id = Column(Integer, primary_key=True)
    mode = Column(String, nullable=False)

class UiUser(Base):
    __tablename__ = 'ui_user'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
