import json
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

app = FastAPI()

DATASET_PATH = Path(__file__).with_suffix("").parent / "retell_mock_full_dataset.json"
if not DATASET_PATH.exists():
    raise FileNotFoundError("retell_mock_full_dataset.json missing")

DATASET: Dict[str, Any] = json.loads(DATASET_PATH.read_text())


# ---------- helper coroutines ----------
async def check_order_status(order_id: str):
    for o in DATASET["orders"]:
        if o["order_id"] == order_id:
            return {"order_id": order_id, "status": o["status"], "delivery_eta": o["delivery_eta"]}
    return {"error": "order_not_found"}


async def get_inventory(product_name: str):
    for p in DATASET["products"]:
        if p["product_name"].lower() == product_name.lower():
            return p
    return {"product_name": product_name, "available_quantity": 0, "availability_status": "out_of_stock"}


async def get_user_profile(user_id: str):
    for u in DATASET["users"]:
        if u["user_id"] == user_id:
            return u
    return {"error": "user_not_found"}


async def handle_fallback(scenario: str):
    for ec in DATASET["edge_cases"]:
        if ec["scenario"] == scenario:
            return {"scenario": scenario, "action": "clarify",
                    "message": "I'm sorry, could you clarify that for me?"}
    return {"scenario": scenario, "action": "escalate",
            "message": "Let me connect you to a human agent."}


FN_MAP = {
    "check_order_status": check_order_status,
    "get_inventory": get_inventory,
    "get_user_profile": get_user_profile,
    "handle_fallback": handle_fallback,
}

# ---------- HTTPS endpoint (Retell Function Node) ----------
@app.post("/fn")
async def call_fn(req: Request):
    body = await req.json()
    fn = body.get("function")
    args = body.get("args", {}) or {}
    if fn not in FN_MAP:
        return JSONResponse({"error": "unknown_function", "function": fn}, status_code=400)
    try:
        result = await FN_MAP[fn](**args)
    except TypeError as e:
        return JSONResponse({"error": "bad_args", "details": str(e)}, status_code=400)
    return {"function": fn, "result": result}

# ---------- Optional WebSocket echo (dev only) ----------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"error": "invalid_json"}))
                continue
            fn = req.get("function")
            args = req.get("args", {}) or {}
            if fn not in FN_MAP:
                await ws.send_text(json.dumps({"error": "unknown_function", "function": fn}))
                continue
            res = await FN_MAP[fn](**args)
            await ws.send_text(json.dumps({"function": fn, "result": res}))
    except WebSocketDisconnect:
        pass
