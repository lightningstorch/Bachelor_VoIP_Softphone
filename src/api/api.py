from typing import List

from fastapi import FastAPI

from datastructure.database.database import get_call_history_lite
from datastructure.dataclass_models import CallHistoryLite

app = FastAPI(title="Call History API")

@app.get("/api/history", response_model=List[CallHistoryLite])
def get_call_history():
    call_history = get_call_history_lite()
    return call_history



