"""FastAPI entry point. Three routes the frontend needs + one for curl tests."""

import json
from pathlib import Path

from dotenv import load_dotenv

# Must run BEFORE graph_topology imports (it reads USE_BEDROCK_OUTCOME at module level).
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

from graph_runner import run_screening_graph
from tools import get_cases_list

app = FastAPI()


@app.get("/cases")
def get_cases():
    return get_cases_list()


@app.post("/screen")
async def screen_case(request: Request):
    """Synchronous run — used by curl/tests."""
    return await run_screening_graph(await request.json())


@app.websocket("/ws/screen")
async def websocket_screen(websocket: WebSocket):
    await websocket.accept()
    try:
        case = await websocket.receive_json()
        await run_screening_graph(case, send_event=websocket.send_json)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "case_id": "unknown", "message": str(e)})
        except Exception:
            pass


@app.post("/feedback")
async def save_feedback(request: Request):
    feedback = await request.json()
    path = Path(__file__).parent / "data" / "feedback_store.json"

    with open(path, "r") as f:
        existing = json.load(f)
    if not isinstance(existing, list):
        existing = []
    existing.append(feedback)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)

    return {"status": "saved", "total_feedback_stored": len(existing)}