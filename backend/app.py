"""FastAPI entry point. Routes the frontend needs + a curl-test screen route."""

import json
from pathlib import Path

from dotenv import load_dotenv

# Must run BEFORE graph_topology imports (it reads LLM_PROVIDER at module level).
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

import chat as chat_module
from graph_runner import run_screening_graph
from tools import get_cases_list

app = FastAPI()


@app.get("/cases")
def get_cases(page: int = 1, page_size: int = 20, search: str = ""):
    return get_cases_list(page=page, page_size=page_size, search=search)


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


@app.post("/chat/starters")
async def chat_starters(request: Request):
    """Return 3 starter questions sized to the case's outcome."""
    body = await request.json()
    case_pack = body.get("case_pack") or {}
    return {"questions": chat_module.starter_questions(case_pack)}


@app.post("/chat/reset")
async def chat_reset(request: Request):
    """Clear the chat conversation for a case (when the user picks a different case)."""
    body = await request.json()
    case_id = body.get("case_id")
    if case_id:
        chat_module.reset_for_case(case_id)
    return {"status": "reset", "case_id": case_id}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Chat protocol:

    Client → server:
      {"type": "init",    "case_id": "...", "state": {...full screening state...}, "reset": true}
      {"type": "message", "text":    "...analyst question..."}

    Server → client:
      {"type": "chunk", "text": "..."}     # streaming token chunks
      {"type": "done",  "elapsed_ms": N, "source": "llm_azure_foundry"|..., "model_id": "..."}
      {"type": "error", "message": "..."}
    """
    await websocket.accept()
    case_id: str | None = None
    state_snapshot: dict | None = None

    try:
        while True:
            msg = await websocket.receive_json()
            kind = msg.get("type")

            if kind == "init":
                case_id = msg.get("case_id")
                state_snapshot = msg.get("state") or {}
                if msg.get("reset") and case_id:
                    chat_module.reset_for_case(case_id)
                continue

            if kind == "message":
                if not case_id or not state_snapshot:
                    await websocket.send_json({"type": "error", "message": "chat not initialised — send {type:'init'} first"})
                    continue

                async def send_chunk(text: str) -> None:
                    await websocket.send_json({"type": "chunk", "text": text})

                result = await chat_module.answer(
                    case_id        = case_id,
                    user_message   = msg.get("text", ""),
                    state_snapshot = state_snapshot,
                    send_chunk     = send_chunk,
                )
                await websocket.send_json({
                    "type":       "done",
                    "elapsed_ms": result["elapsed_ms"],
                    "source":     result["source"],
                    "model_id":   result["model_id"],
                })
                continue

            await websocket.send_json({"type": "error", "message": f"unknown message type: {kind!r}"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
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
