from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Calls(Base):
    __tablename__ = 'calls'
    id = Column(String, primary_key=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    # relationship to participants
    participants = relationship("Participants", back_populates="call")


class Participants(Base):
    __tablename__ = 'participants'
    id = Column(Integer, primary_key=True)
    call_id = Column(String, ForeignKey('calls.id'), nullable=False)
    user = Column(String, nullable=False)
    media_port = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=True)

    # relationship to calls
    call = relationship("Calls", back_populates="participants")

    # relationship to talking_section
    talking_sections = relationship("TalkingSections", back_populates="participant")


class TalkingSections(Base):
    __tablename__ = 'talking_sections'
    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey('participants.id'), nullable=False)
    section_start = Column(DateTime, nullable=False)
    section_end = Column(DateTime, nullable=False)

    participant = relationship("Participants", back_populates="talking_sections")

