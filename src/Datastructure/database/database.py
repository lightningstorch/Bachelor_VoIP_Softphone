
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.config import database_type, database_connection
from datastructure.database.models import Base, Calls, Participants
from datastructure.dataclass_models import CallInfo
from my_logging.log_config import app_logger

engine = create_engine(
    database_connection,
    connect_args={"check_same_thread": False} if database_type == "sqlite" else {},
)

Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)


def store_call_start(call_id: str, call_info: CallInfo):

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
    session = Session()

    call = session.get(Calls, call_id)
    if call:
        call.end_time = call_info.end_time
        session.commit()
        app_logger.debug(f"Call ID '{call_id}' has been updated in db")
        print(f"Call ID '{call_id}' has been updated in db")
    else:
        app_logger.warning(f"Call ID '{call_id}' not found in db")
        print(f"Call ID '{call_id}' not found in db")

    session.close()

