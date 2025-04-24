from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# Request models
class OrderRequest(BaseModel):
    order_id: str

class RefundRequest(BaseModel):
    order_id: str
    reason: str

class TicketRequest(BaseModel):
    issue_type: str
    user_notes: str
    order_id: str = None

class LogRequest(BaseModel):
    call_summary: str
    sentiment: str
    timestamp: str

# Routes
@app.post("/check_order_status")
async def check_order_status(req: OrderRequest):
    return {
        "order_id": req.order_id,
        "status": "preparing",
        "delivery_eta": "57 min",
        "delivered_at": None
    }

@app.post("/cancel_order")
async def cancel_order(req: OrderRequest):
    return {
        "cancelled": True,
        "note": f"Order {req.order_id} was cancelled successfully."
    }

@app.post("/request_refund")
async def request_refund(req: RefundRequest):
    return {
        "approved": True,
        "note": f"Refund for order {req.order_id} has been processed due to: {req.reason}"
    }

@app.post("/create_ticket")
async def create_ticket(req: TicketRequest):
    return {
        "ticket_created": True,
        "note": f"Ticket created for issue: {req.issue_type}. Notes: {req.user_notes}"
    }

@app.post("/log_call")
async def log_call(req: LogRequest):
    return {
        "logged": True,
        "note": f"Call logged with sentiment: {req.sentiment} and summary: {req.call_summary}"
    }

@app.post("/get_current_datetime")
async def get_current_datetime():
    now = datetime.now()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S")
    }

@app.post("/end_call")
async def end_call():
    return {"end_call": True}

