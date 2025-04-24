# Volt Mock Data & API Backend

This repository provides mock data and a simple WebSocket backend implementation for the Volt Voice AI Agent, designed and deployed using Retell.ai. It supports simulation testing, allowing realistic testing scenarios without connecting to real customer data or backend systems.

## 🚀 Purpose
- Simulate realistic API responses for Volt AI agent function nodes:
  - `check_order_status`
  - `cancel_order`
  - `request_refund`
  - `create_ticket`
  - `get_current_datetime`
  - `log_call`

## 🛠️ Technical Details
- Simple FastAPI implementation serving mocked API responses via WebSocket.
- JSON-based mock dataset for orders, refunds, cancellations, and escalations.

## ⚙️ Usage
- Run locally or deploy using Docker:
```bash
docker build -t volt-retell-backend .
docker run -p 8000:8000 volt-retell-backend
