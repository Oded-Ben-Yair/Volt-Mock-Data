"""
main.py – FastAPI middleware for Retell.ai tool‑calls
----------------------------------------------------
• Works with **either** the mock JSON dataset (env `DATA_FILE`) **or** an in‑memory stub.
• Keeps exactly the schema Retell passes when it calls a Function node: **just the tool
  arguments** in the request body (e.g. `{"order_id": "A3927"}`), so we never hit a
  422 again.
• Returns clean, JSON‑serialisable data – nothing Retell can’t parse – and **always** a
  `200 OK`, falling back to an `error` key when something’s wrong so the agent can ask
  clarifying questions instead of hanging up.

If you need additional endpoints, copy the pattern used below – each accepts the raw
arguments payload in a pydantic model and spits back a self‑contained JSON response.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Volt Support Tool API", version="0.4.0")

###############################################################################
# ─── DATA LOADING ────────────────────────────────────────────────────────────
###############################################################################

def _load_dataset() -> dict:
    """Load mock dataset from DATA_FILE env or return an in‑memory stub."""
    path = os.getenv("DATA_FILE")
    if path and Path(path).is_file():
        try:
            with open(path, "r", encoding="utf‑8") as f:
                return json.load(f)
        except Exception as exc:  # noqa: BLE001
            print("[WARN] Failed reading dataset:", exc)
    # ── fallback stub ────────────────────────────────────────────────────────
    print("[INFO] Using in‑memory stub dataset – order status will be random.")
    return {
        "orders": [
            {
                "order_id": "A0000",
                "status": "preparing",
                "delivery_eta": "45 min",
                "delivered_at": None,
            }
        ]
    }

db = _load_dataset()

###############################################################################
# ─── SCHEMAS ─────────────────────────────────────────────────────────────────
###############################################################################

class CheckOrderStatusIn(BaseModel):
    order_id: str = Field(..., examples=["A3927"])

class CheckOrderStatusOut(BaseModel):
    order_id: str
    status: str
    delivery_eta: Optional[str] = None
    delivered_at: Optional[str] = None
    error: Optional[str] = None

###############################################################################
# ─── HELPERS ────────────────────────────────────────────────────────────────
###############################################################################

def _find_order(order_id: str) -> Optional[dict]:
    for rec in db.get("orders", []):
        if rec.get("order_id") == order_id:
            return rec
    return None

###############################################################################
# ─── ENDPOINTS ──────────────────────────────────────────────────────────────
###############################################################################

@app.get("/health")
async def health():
    """Health probe used by Render / Fly.io etc."""
    return {"status": "ok", "time": datetime.utcnow().isoformat()}  # simple and fast


@app.post("/check_order_status", response_model=CheckOrderStatusOut)
async def check_order_status(payload: CheckOrderStatusIn):
    """Return status/ETA for an existing order.

    Retell will call this with **only** the tool‑arguments, so FastAPI must parse that
    directly – no extra wrapper keys.
    """
    rec = _find_order(payload.order_id)
    if not rec:
        # 200 to Retell but with error info – the agent can then ask for a different ID.
        return CheckOrderStatusOut(order_id=payload.order_id, status="unknown", error="Order not found")

    return CheckOrderStatusOut(
        order_id=rec["order_id"],
        status=rec["status"],
        delivery_eta=rec.get("delivery_eta"),
        delivered_at=rec.get("delivered_at"),
    )

###############################################################################
# Add more endpoints following the same pattern whenever you wire additional
# Function nodes (cancel_order, request_refund, etc.).
###############################################################################

