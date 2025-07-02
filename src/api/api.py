import os
from typing import List

from fastapi import FastAPI, HTTPException, WebSocket

from datastructure.database.database import get_call_history_lite, get_full_call_data
from datastructure.dataclass_models import CallHistoryLite, CallDetail

app = FastAPI(title="Call History API")

@app.get("/api/history", response_model=List[CallHistoryLite])
def get_call_history():
    return get_call_history_lite()

@app.get("/api/call-details", response_model=CallDetail)
def get_call_details(call_id: str):
    call = get_full_call_data(call_id)
    if not call:
        return HTTPException(status_code=404, detail="Call not found")
    return call
