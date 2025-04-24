"""
Volt × Retell mock back-end
—————————————
FastAPI service that implements the function‑tool contract Retell.ai expects.
It loads mock data from retell_mock_full_dataset.json that lives **next to
this file** by default, but the path can be overridden with DATA_FILE env‑var.

Version 1.1 — identical to the proven‑stable build except for ONE addition:
    • **/end_call** endpoint that lets the LLM hang up gracefully by returning
      `{ "ok": true, "data": { "hang_up": true } }`
All other behaviour, helpers, and payload formats remain untouched.
"""

import json
import os
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# ••• DATA LOADING •••
# --------------------------------------------------------------------------- #
BASE_DIR = pathlib.Path(__file__).parent
DATA_FILE = pathlib.Path(os.getenv("DATA_FILE", BASE_DIR / "retell_mock_full_dataset.json")).resolve()

if not DATA_FILE.exists():
    raise RuntimeError(
        f"❌  DATA_FILE not found at {DATA_FILE}. "
        "Mount it there or export DATA_FILE=/absolute/path.json"
    )

with DATA_FILE.open(encoding="utf-8") as f:
    DATA: Dict[str, Any] = json.load(f)

ORDERS = {o["order_id"]: o for o in DATA["orders"]}

# --------------------------------------------------------------------------- #
# ••• FASTAPI APP •••
# --------------------------------------------------------------------------- #
app = FastAPI(title="Volt Retell Mock Functions")


# ----------- Helper -------------------------------------------------------- #

def tool_ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "data": payload}


def tool_err(message: str, code: int = 400) -> Dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def save():  # In-memory only for mock; extend if persistence is required
    pass


# ----------- Request / Response Schemas ----------------------------------- #
class ArgsWrapper(BaseModel):
    """Matches Retell's { "args": { … } } envelope."""

    args: Dict[str, Any] = Field(...)


# --------------------------------------------------------------------------- #
# ••• FUNCTION ENDPOINTS •••
# --------------------------------------------------------------------------- #

@app.post("/check_order_status")
def check_order_status(payload: ArgsWrapper):

    # PII filter: Detect credit card numbers (simple pattern)
    user_input = json.dumps(payload.args)
    if re.search(r"\b\d{4} \d{4} \d{4} \d{4}\b", user_input):
        return tool_err("Sensitive information like credit card numbers is not allowed.", 403)
    order_id = payload.args.get("order_id")
    order = ORDERS.get(order_id)
    if not order:
        return tool_err(f"Order {order_id} not found", 404)
    return tool_ok(
        {
            "order_id": order_id,
            "status": order["status"],
            "delivery_eta": order["delivery_eta"],
            "delivered_at": order["delivered_at"],
        }
    )


@app.post("/cancel_order")
def cancel_order(payload: ArgsWrapper):

    # PII filter: Detect credit card numbers (simple pattern)
    user_input = json.dumps(payload.args)
    if re.search(r"\b\d{4} \d{4} \d{4} \d{4}\b", user_input):
        return tool_err("Sensitive information like credit card numbers is not allowed.", 403)
    order_id = payload.args.get("order_id")
    order = ORDERS.get(order_id)
    if not order:
        return tool_err(f"Order {order_id} not found", 404)
    if not order["can_cancel"] or order["status"] in {"dispatched", "delivered", "cancelled"}:
        return tool_err("Order can no longer be cancelled", 400)

    order["status"] = "cancelled"
    order["can_cancel"] = False
    save()
    return tool_ok({"order_id": order_id, "message": "Order cancelled successfully"})


@app.post("/request_refund")
def request_refund(payload: ArgsWrapper):

    # PII filter: Detect credit card numbers (simple pattern)
    user_input = json.dumps(payload.args)
    if re.search(r"\b\d{4} \d{4} \d{4} \d{4}\b", user_input):
        return tool_err("Sensitive information like credit card numbers is not allowed.", 403)
    order_id = payload.args.get("order_id")
    reason = payload.args.get("reason", "unspecified")
    order = ORDERS.get(order_id)
    if not order:
        return tool_err(f"Order {order_id} not found", 404)
    if not order["eligible_for_refund"]:
        return tool_err("Order not eligible for refund", 400)

    refund_amount = round(sum(i["qty"] * 5 for i in order["items"]), 2)  # mock calc
    order["eligible_for_refund"] = False
    save()
    return tool_ok(
        {
            "order_id": order_id,
            "approved": True,
            "refund_amount": refund_amount,
            "reason": reason,
        }
    )


@app.post("/create_ticket")
def create_ticket(payload: ArgsWrapper):

    # PII filter: Detect credit card numbers (simple pattern)
    user_input = json.dumps(payload.args)
    if re.search(r"\b\d{4} \d{4} \d{4} \d{4}\b", user_input):
        return tool_err("Sensitive information like credit card numbers is not allowed.", 403)
    ticket_id = f"volt-{uuid.uuid4().hex[:8]}"
    return tool_ok(
        {
            "ticket_id": ticket_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "details": payload.args,
        }
    )


@app.post("/log_call")
def log_call(payload: ArgsWrapper):

    # PII filter: Detect credit card numbers (simple pattern)
    user_input = json.dumps(payload.args)
    if re.search(r"\b\d{4} \d{4} \d{4} \d{4}\b", user_input):
        return tool_err("Sensitive information like credit card numbers is not allowed.", 403)
    # Normally you'd push to Slack / DB; here we just echo.
    return tool_ok({"stored": True, "received": payload.args})


@app.post("/get_current_datetime")
def get_current_datetime(_: ArgsWrapper):
    now = datetime.now(timezone.utc)
    return tool_ok({"date": now.date().isoformat(), "time": now.time().isoformat(timespec="seconds")})


# ----------- NEW: explicit end‑call hook ---------------------------------- #

@app.post("/end_call")
def end_call(_: ArgsWrapper):
    """Signal Retell to terminate the call cleanly."""
    return tool_ok({"hang_up": True})


# --------------------------------------------------------------------------- #
# ••• MISC •••
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok", "dataset_rows": len(ORDERS)}

