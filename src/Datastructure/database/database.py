
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from config.config import database_type, database_connection
from datastructure.database.models import Base, Calls, Participants, TalkingSections
from datastructure.dataclass_models import CallInfo, TalkingInterval, EventType
from my_logging.log_config import app_logger

engine = create_engine(
    database_connection,
    connect_args={"check_same_thread": False} if database_type == "sqlite" else {},
)

Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)


def store_call_start(call_id: str, call_info: CallInfo):
    """
    Store the start of a call in the database.
    This function checks if the call ID already exists in the database.
    If it does, it logs a message and returns without making any changes.
    :param call_id: The unique identifier for the call.
    :param call_info: The CallInfo object containing details about the call.
    """
    session = Session()

    if session.get(Calls, call_id):
        app_logger.debug(f"Call ID '{call_id}' already exists in db")
        print(f"Call ID '{call_id}' already exists in db")
        session.close()
        return

    try:
        new_call = Calls(
            id=call_id,
            start_time=call_info.start_time,
            end_time=call_info.end_time
        )
        session.add(new_call)

        for participant in call_info.participants:
            new_participant = Participants(
                call_id=call_id,
                user=participant.user,
                ip_address=participant.ip_address,
                media_port=participant.media_port,
                mime_type=participant.mime_type,
                server_ip=participant.server_ip,
                server_port=participant.server_port,
                ssrc=participant.ssrc
            )
            session.add(new_participant)

        session.commit()
        print(f"Call ID '{call_id}' has been commited to db")
        app_logger.debug(f"Call ID '{call_id}' has been stored in db")
    except Exception as e:
        session.rollback()
        app_logger.error(f"Error with rollback while storing call id '{call_id}' in db: {e}")
        print(f"Error with rollback while storing call id '{call_id}' in db: {e}")

    finally:
        session.close()

def store_call_end(call_id: str, call_info: CallInfo):
    """
    Store the end of a call in the database.
    This function updates the end time of an existing call in the database.
    :param call_id: The unique identifier for the call.
    :param call_info: The CallInfo object containing details about the call, specifically the end time.
    """
    session = Session()

    call = session.get(Calls, call_id)
    if call:
        try:
            call.end_time = call_info.end_time
            session.commit()
            app_logger.debug(f"Call ID '{call_id}' has been updated in db")
            print(f"Call ID '{call_id}' has been updated in db")
        except Exception as e:
            app_logger.error(f"Error with rollback while updating the end time of call id '{call_id}' in db: {e}")
            session.rollback()
    else:
        app_logger.warning(f"Call ID '{call_id}' not found in db")
        print(f"Call ID '{call_id}' not found in db")

    session.close()

def store_ssrc(call_id: str, ssrc: str, user: str):
    """
    Store the SSRC (Synchronization Source) for a participant in a call.
    This function updates the SSRC for a participant in the database.
    :param call_id: The unique identifier for the call.
    :param ssrc: The SSRC to be stored.
    :param user: The user associated with the SSRC.
    """
    session = Session()

    participant = session.query(Participants).filter_by(call_id=call_id, user=user).one_or_none()
    if participant:
        try:
            participant.ssrc = str(ssrc)
            session.commit()
            app_logger.debug(f"SSRC '{ssrc}' has been updated for call ID '{call_id}' in db")
            print(f"SSRC '{ssrc}' has been updated for call ID '{call_id}' in db")
        except Exception as e:
            session.rollback()
            app_logger.error(f"Error with rollback while updating SSRC '{ssrc}' for call ID '{call_id}' in db: {e}")
    else:
        app_logger.warning(f"Call ID '{call_id}' not found in db")
        print(f"Call ID '{call_id}' not found in db")

    session.close()

def store_talking_sections(talking_interval: TalkingInterval):
    session = Session()

    call_id = talking_interval.call_id
    ssrc = talking_interval.ssrc

    try:

        if talking_interval.type == "speech":
            participant_id = session.query(Participants.id).filter_by(call_id=call_id, ssrc=ssrc).scalar()
        else:
            participant_id = None

        new_section = TalkingSections(
            call_id=call_id,
            participant_id=participant_id,
            type=talking_interval.type,
            section_start=talking_interval.start,
            section_end=talking_interval.end
        )
        session.add(new_section)

        session.commit()
        app_logger.debug(f"Talking sections for call ID '{call_id}' and SSRC '{ssrc}' have been stored in db")

    except IntegrityError:
        session.rollback()
        app_logger.warning(
            f"Talking section '{talking_interval.start} - {talking_interval.end}' "
            f"for call ID '{call_id}' and SSRC '{ssrc}' already exists in db"
        )
    except Exception as e:
        session.rollback()
        app_logger.error(f"Error while storing talking sections for call ID '{call_id}' and SSRC '{ssrc}': {e}")

    finally:
        session.close()
