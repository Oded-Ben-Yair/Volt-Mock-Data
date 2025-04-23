"""
main.py – FastAPI middleware for Retell.ai tool‑calls
----------------------------------------------------
• Accepts **either** payload style Retell currently sends:
  – _Flat_: `{ "order_id": "A3927" }`
  – _Wrapped_: `{ "args": { "order_id": "A3927", "execution_message": "…" } }`
  so we never hit a 422 again.
• Returns a stable envelope Retell can parse: `{"ok": true|false, "data"|"error": …}`.
• Adds an **/end_call** endpoint (and an `end_call` helper) so the LLM can explicitly
  terminate the call with `{"ok": true, "data": {"hang_up": true}}` – Retell treats this as
  a clean "<END CALL>" marker and closes the connection automatically.
• Keeps all responses `200 OK`; errors surface in JSON so the voice agent can recover
  (e.g. “Could you read that ID back for me?”) instead of hanging up.
• Minimal stub dataset ships in‑memory; drop a richer JSON file via `DATA_FILE` env
  to override.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Volt Support Tool API", version="0.6.0")

###############################################################################
# ─── DATA LOADING ────────────────────────────────────────────────────────────
###############################################################################

DATA_FILE = os.getenv("DATA_FILE")

if DATA_FILE and Path(DATA_FILE).is_file():
    try:
        with open(DATA_FILE, "r", encoding="utf‑8") as f:
            _db: Dict[str, Any] = json.load(f)
    except Exception as exc:  # noqa: BLE001
        print("[WARN] Failed reading dataset:", exc)
        _db = {}
else:
    print("[INFO] Using in‑memory stub dataset – override with $DATA_FILE if needed")
    _db = {
        "orders": [
            {
                "order_id": "A0000",
                "status": "preparing",
                "delivery_eta": "45 min",
                "delivered_at": None,
                "can_cancel": True,
                "eligible_for_refund": False,
                "items": [{"product_name": "Coffee", "qty": 1}],
            }
        ]
    }

def _find_order(order_id: str) -> Optional[dict]:
    for rec in _db.get("orders", []):
        if rec.get("order_id") == order_id:
            return rec
    return None

###############################################################################
# ─── RESPONSE HELPERS ────────────────────────────────────────────────────────
###############################################################################

def _ok(data: Dict[str, Any] | None = None, *, hang_up: bool = False) -> Dict[str, Any]:
    """Standard success envelope. If *hang_up* is True we signal Retell to
    terminate the call by adding `{"hang_up": true}` inside *data*.
    """
    payload: Dict[str, Any] = {}
    if data:
        payload.update(data)
    if hang_up:
        payload["hang_up"] = True  # Retell interprets this flag as <END CALL>
    return {"ok": True, "data": payload}


def _err(msg: str, code: int = 400) -> Dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": msg}}

###############################################################################
# ─── UTILS ───────────────────────────────────────────────────────────────────
###############################################################################

class _Payload(BaseModel):
    """Generic wrapper to accept *any* JSON – validated later."""
    __root__: Dict[str, Any]


def _extract_order_id(payload: Dict[str, Any]) -> Optional[str]:
    """Handle both flat and Retell‑wrapped payloads."""
    if "order_id" in payload:
        return payload["order_id"]
    if "args" in payload and isinstance(payload["args"], dict):
        return payload["args"].get("order_id")
    return None

###############################################################################
# ─── HEALTH ──────────────────────────────────────────────────────────────────
###############################################################################

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

###############################################################################
# ─── CORE ENDPOINTS ─────────────────────────────────────────────────────────
###############################################################################

@app.post("/check_order_status")
async def check_order_status(raw: _Payload):
    payload = raw.__root__
    order_id = _extract_order_id(payload)
    if not order_id:
        return _err("order_id missing from payload", 422)

    rec = _find_order(order_id)
    if not rec:
        return _err(f"Order {order_id} not found", 404)

    return _ok(
        {
            "order_id": rec["order_id"],
            "status": rec["status"],
            "delivery_eta": rec.get("delivery_eta"),
            "delivered_at": rec.get("delivered_at"),
        }
    )


@app.post("/cancel_order")
async def cancel_order(raw: _Payload):
    payload = raw.__root__
    order_id = _extract_order_id(payload)
    if not order_id:
        return _err("order_id missing from payload", 422)

    rec = _find_order(order_id)
    if not rec:
        return _err(f"Order {order_id} not found", 404)
    if not rec.get("can_cancel", False) or rec["status"] in {"dispatched", "delivered", "cancelled"}:
        return _err("Order can no longer be cancelled", 400)

    rec["status"] = "cancelled"
    rec["can_cancel"] = False
    return _ok({"order_id": order_id, "message": "Order cancelled successfully"})


@app.post("/request_refund")
async def request_refund(raw: _Payload):
    payload = raw.__root__
    order_id = _extract_order_id(payload)
    reason = (
        payload.get("reason")
        or payload.get("args", {}).get("reason")
        or "unspecified"
    )
    if not order_id:
        return _err("order_id missing from payload", 422)

    rec = _find_order(order_id)
    if not rec:
        return _err(f"Order {order_id} not found", 404)
    if not rec.get("eligible_for_refund", False):
        return _err("Order not eligible for refund", 400)

    refund_amount = round(sum(i.get("qty", 0) * 5 for i in rec.get("items", [])), 2)  # mock calc
    rec["eligible_for_refund"] = False
    return _ok(
        {
            "order_id": order_id,
            "approved": True,
            "refund_amount": refund_amount,
            "reason": reason,
        }
    )


@app.post("/create_ticket")
async def create_ticket(raw: _Payload):
    args = raw.__root__.get("args", raw.__root__)
    ticket_id = f"volt-{uuid.uuid4().hex[:8]}"
    return _ok(
        {
            "ticket_id": ticket_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "details": args,
        }
    )


@app.post("/log_call")
async def log_call(raw: _Payload):
    return _ok({"stored": True, "received": raw.__root__})


@app.post("/get_current_datetime")
async def get_current_datetime(_: _Payload):
    now = datetime.now(timezone.utc)
    return _ok({"date": now.date().isoformat(), "time": now.time().isoformat(timespec="seconds")})

###############################################################################
# ─── END CALL HANDLER ───────────────────────────────────────────────────────
###############################################################################

@app.post("/end_call")
async def end_call(raw: _Payload):  # payload ignored – LLM just calls the tool
    """Explicitly tell Retell to hang up. The voice agent should call this when the
    conversation goal is reached, e.g. after reading the final status or confirming
    a refund. Retell closes the call as soon as it sees `hang_up: true` in the JSON.
    """
    return _ok({}, hang_up=True)

###############################################################################
# Add further endpoints following the same pattern – remember to use `_ok()` so
# the voice agent can always parse the response, and `_err()` when something
# goes wrong so it can recover instead of crashing.                           
###############################################################################

