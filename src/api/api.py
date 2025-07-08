import os
import tempfile
from typing import List, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, Form, File, UploadFile

from datastructure.database.database import get_call_history_lite, get_full_call_data, get_program_mode, \
    set_program_mode
from datastructure.dataclass_models import CallHistoryLite, CallDetail
from config.config import interface
from main import start_capture_provider

#===================================
#         FastAPI Application
#===================================
app = FastAPI(title="Call History API")

# Temporary directory for file uploads
UPLOAD_DIR = tempfile.gettempdir()


def start_api():
    """
    Starts the FastAPI application in a separate thread.
    """
    uvicorn.run("api.api:app", host="0.0.0.0", port=8000, log_level="warning")


#===================================
#         API Endpoints
#===================================

@app.get("/api/history", response_model=List[CallHistoryLite])
def get_call_history():
    """
    Fetches minimal information of the calls from the database.
    :return: The call history with minimal information.
    """
    return get_call_history_lite()


@app.get("/api/call-details", response_model=CallDetail)
def get_call_details(call_id: str):
    """
    Fetches detailed information about a specific call by its ID.
    :param call_id: The unique identifier of the call.
    :return: The detailed information of the call.
    """
    call = get_full_call_data(call_id)
    if not call:
        return HTTPException(status_code=404, detail="Call not found")
    return call


@app.post("/api/mode")
async def change_mode(mode: Literal["live", "file"] = Form(...), file: UploadFile | None = File(None)):
    current_mode = get_program_mode()
    if mode == "live" and current_mode != "live":
        start_capture_provider(mode, interface)
        set_program_mode("live")
        return {"mode": "live", "using": interface}

    elif mode == "file":
        if not file:
            raise HTTPException(status_code=400, detail="File is required for file mode")

        save_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(save_path, "wb") as f:
            f.write(await file.read())
        start_capture_provider(mode, save_path)
        set_program_mode("file")

        return {"mode": "file", "using": save_path}

    return None


@app.get("/api/server-mode")
def get_program_mode_endpoint():
    """
    Returns the current program mode (live or file).
    """
    mode = get_program_mode()
    if not mode:
        raise HTTPException(status_code=404, detail="Program mode not set")
    return {"mode": mode}
