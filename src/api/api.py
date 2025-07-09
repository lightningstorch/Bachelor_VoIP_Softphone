import os
import tempfile

from typing import List, Literal

from datastructure.database.models import UiUser
from fastapi import FastAPI, HTTPException, WebSocket, Form, File, UploadFile, Depends
from datastructure.database.database import get_call_history_lite, get_full_call_data, get_program_mode, \
    set_program_mode
from datastructure.dataclass_models import CallHistoryLite, CallDetail
from config.config import interface
from fastapi.security import OAuth2PasswordRequestForm
from main import start_capture_provider, switch_mode
from utils.auth import authenticate, create_token, verify_token

#===================================
#         FastAPI Application
#===================================
app = FastAPI(title="Call History API")

# Temporary directory for file uploads
UPLOAD_DIR = tempfile.gettempdir()

#===================================
#         API Endpoints
#===================================

@app.get("/api/history", response_model=List[CallHistoryLite])
def get_call_history(current_user: UiUser = Depends(verify_token)):
    """
    Fetches minimal information of the calls from the database.
    :param current_user: To ensure, the user is authenticated.
    :return: The call history with minimal information.
    """
    return get_call_history_lite()

@app.get("/api/call-details", response_model=CallDetail)
def get_call_details(call_id: str, current_user: UiUser = Depends(verify_token)):
    """
    Fetches detailed information about a specific call by its ID.
    :param current_user: To ensure, the user is authenticated.
    :param call_id: The unique identifier of the call.
    :return: The detailed information of the call.
    """
    call = get_full_call_data(call_id)
    if not call:
        return HTTPException(status_code=404, detail="Call not found")
    return call

@app.post("/api/mode")
async def change_mode(
        mode: Literal["live", "file"] = Form(...),
        file: UploadFile | None = File(None),
        current_user: UiUser = Depends(verify_token)
):
    """
    Changes the program mode to either live or file.
    If the mode is set to "live", it will switch to live capture using the specified interface.
    If the mode is set to "file", it will save the uploaded file and switch to file mode.
    :param mode: The mode to switch to, either "live" or "file".
    :param file: The file to upload if the mode is "file". This should be a PCAP or PCAPNG file.
    :param current_user: To ensure, the user is authenticated.
    :return: A dictionary indicating the new mode and the source being used.
    """
    current_mode = get_program_mode()
    if mode == "live" and current_mode != "live":
        switch_mode(mode, interface)
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
def get_program_mode_endpoint(current_user: UiUser = Depends(verify_token)):
    """
    Returns the current program mode (live or file).
    :param current_user: To ensure, the user is authenticated.
    """
    mode = get_program_mode()
    if not mode:
        raise HTTPException(status_code=404, detail="Program mode not set")
    return {"mode": mode}

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

