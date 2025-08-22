import asyncio
import json
import os
import tempfile

from contextlib import asynccontextmanager
from typing import List, Literal
from sse_starlette.sse import EventSourceResponse
from datastructure.database.models import UiUser
from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from datastructure.database.database import (get_call_history_lite, get_call_for_api,
                                             get_user, change_password, set_user, remove_user)
from datastructure.dataclass_models import CallHistoryLite, CallDetail
from config.config import interface
from fastapi.security import OAuth2PasswordRequestForm
from main import switch_mode
from utils.auth import authenticate, create_token, verify_token_oauth, verify_token, verify_password, hash_password
from my_logging.log_config import event_queue, set_event_loop, app_logger
from utils.program_state_manager import ProgramStateManager


#===================================
#         FastAPI Application
#===================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for the FastAPI application. And start the asyncio event loop.
    :param app: The FastAPI application instance.
    :return: Yields control to the application during its lifespan.
    """
    loop = asyncio.get_running_loop()
    set_event_loop(loop)
    yield

app = FastAPI(title="Call History API", lifespan=lifespan)

# Temporary directory for file uploads
UPLOAD_DIR = tempfile.gettempdir()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

#===================================
#         API Endpoints
#===================================

@app.get("/api/history", response_model=List[CallHistoryLite])
def get_call_history(current_user: UiUser = Depends(verify_token_oauth)):
    """
    Fetches minimal information of the calls from the database.
    :param current_user: To ensure, the user is authenticated.
    :return: The call history with minimal information.
    """
    return get_call_history_lite()

@app.get("/api/call-details", response_model=CallDetail)
def get_call_details(call_id: str, current_user: UiUser = Depends(verify_token_oauth)):
    """
    Fetches detailed information about a specific call by its ID.
    :param current_user: To ensure, the user is authenticated.
    :param call_id: The unique identifier of the call.
    :return: The detailed information of the call.
    """
    call = get_call_for_api(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call

@app.post("/api/mode")
async def change_mode(
        mode: Literal["live", "file"] = Form(...),
        file: UploadFile | None = File(None),
        current_user: UiUser = Depends(verify_token_oauth)
):
    """
    Changes the program mode to either live or file.
    If the mode is set to "live", it changes the mode to live capture, because the live capture is already running.
    If the mode is set to "file", it will save the uploaded file and switch to file mode.
    :param mode: The mode to switch to either "live" or "file".
    :param file: The file to upload if the mode is "file". This should be a PCAP or PCAPNG file.
    :param current_user: To ensure, the user is authenticated.
    :return: A dictionary indicating the new mode and the source being used.
    """
    state_manager = ProgramStateManager()

    if mode == "live" and state_manager.get_mode() != "live":
        # the live capture is already running, because the live capture isn't stopped
        state_manager.switch_mode("live", interface)
        return {"mode": "live", "using": interface}

    elif mode == "file":
        if not file:
            raise HTTPException(status_code=400, detail="File is required for file mode")

        save_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(save_path, "wb") as f:
            f.write(await file.read())
        switch_mode(mode, save_path)

        return {"mode": "file", "using": save_path}

    return None

@app.get("/api/server-mode")
def get_program_mode_endpoint(current_user: UiUser = Depends(verify_token_oauth)):
    """
    Returns the current mode of the program.
    :param current_user: To ensure, the user is authenticated.
    """
    state_manager = ProgramStateManager()
    if state_manager.get_mode() is None:
        raise HTTPException(status_code=404, detail="Program mode not set")
    return {"mode": state_manager.get_mode()}


@app.post("/api/change-password")
def set_new_password(
        old_password: str = Form(...),
        new_password: str = Form(...),
        current_user: UiUser = Depends(verify_token_oauth)
):
    """
    Changes the password for the current user.
    :param old_password: The current password of the user.
    :param new_password: The new password to set for the user.
    :param current_user: The currently authenticated user.
    :return: A dictionary indicating success or failure of the password change.
    """
    if verify_password(old_password, current_user.password):
        # Hash the new password and update it in the database
        hashed_new_password = hash_password(new_password)
        change_password(current_user.username, hashed_new_password)
        return {"success": True, "message": "Password changed successfully"}
    else:
        raise HTTPException(status_code=401, detail="Old password is incorrect")

@app.post("/api/create-user")
def set_new_user(
        username: str = Form(...),
        password: str = Form(...),
        current_user: UiUser = Depends(verify_token_oauth)
):
    """
    Creates a new user with the provided username and password.
    :param username: The username for the new user.
    :param password: The password for the new user.
    :param current_user: The currently authenticated user, to ensure only authorized users can create new users.
    :return: A dictionary indicating success or failure of user creation.
    """
    hashed_new_password = hash_password(password)
    new_user = set_user(username, hashed_new_password)

    if new_user is None:
        raise HTTPException(status_code=401, detail="User already exists")

    if not new_user:
        return {"success": False, "message": "Failed to create user"}

    return {"success": True, "message": "User created successfully"}

@app.post("/api/delete-user")
def delete_user(
        username: str = Form(...),
        password: str = Form(...),
        current_user: UiUser = Depends(verify_token_oauth)
):
    """
    Deletes a user with the provided username and password.
    :param username: The username of the user to delete.
    :param password: The password of the user to delete.
    :param current_user: The currently authenticated user, to ensure only authorized users can delete users.
    :return: A dictionary indicating success or failure of user deletion.
    """
    existing_user = get_user(username)
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(password, existing_user.password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    if remove_user(username):
        return {"success": True, "message": "User deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete user")


@app.get("/api/health-check")
def health_check(
        current_user: UiUser = Depends(verify_token_oauth)
):
    """
    A simple health check endpoint to verify the API is running.
    :param current_user: To ensure, the user is authenticated.
    :return: A dictionary indicating the API is healthy.
    """
    return {"status": "healthy"}


#===================================
#         Login Actions
#===================================

@app.post("/api/login")
async def login(from_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates a user and returns an access token if successful.
    :param from_data: The form data containing username and password.
    :return: A dictionary containing the access token and its type if authentication is successful.
    """
    if authenticate(from_data.username, from_data.password) is not None:
        token = create_token(from_data.username)
        return {"access_token": token, "token_type": "bearer"}

    raise HTTPException(status_code=401, detail="Invalid credentials")


#===========================================================
#         SSE (Server-Sent Events) Client Functions
#===========================================================

@app.get("/api/logs/stream")
async def log_stream(
        request: Request,
        current_user: UiUser = Depends(verify_token_oauth)
):
    """
    SSE endpoint for authenticated clients to receive real-time log updates.
    """
    print("🟢 [SSE] New client connected")
    app_logger.info("New sse-client connected")

    return EventSourceResponse(event_generator(request))

@app.get("/api/logs/stream-browser")
async def log_stream_browser(request: Request, token: str = Query(..., min_length=10)):
    """
    SSE endpoint for browser clients. The token is passed as a query parameter.
    """
    _user = verify_token(token)
    return EventSourceResponse(event_generator(request))


async def event_generator(request: Request):
    """
    Generator function to yield log events to the SSE client.
    Sends log events from the event queue to the client.
    If no events are available within 15 seconds, sends a keep-alive ping.
    If the client disconnects, the generator stops.
    :param request: The incoming HTTP request.
    :return: The event data to be sent to the client.
    """

    while True:
        if await request.is_disconnected():
            break

        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=15)

            payload = {
                "type": event["type"],
                "payload": event["payload"]
            }

            yield {
                "event": "log",
                "data": json.dumps(payload)
            }

        except asyncio.TimeoutError:
            yield {
                "event": "keep-alive",
                "data": "ping"
            }
