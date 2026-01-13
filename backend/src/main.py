from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from .schemas import TelemetryEvent, DecisionLog

app = FastAPI(title="FlowGuard Telemetry Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for demo purposes
event_log: List[TelemetryEvent] = []
decisions: List[DecisionLog] = []

@app.post("/api/v1/telemetry/event")
async def ingest_event(event: TelemetryEvent):
    event_log.append(event)
    return {"status": "received", "count": len(event_log)}

@app.post("/api/v1/telemetry/decision")
async def ingest_decision(decision: DecisionLog):
    decisions.append(decision)
    # in a real app, write to DB or TimescaleDB here
    return {"status": "logged", "total_decisions": len(decisions)}

@app.get("/api/v1/dashboard/summary")
async def get_dashboard_summary():
    return {
        "total_events": len(event_log),
        "total_decisions": len(decisions),
        "recent_decisions": decisions[-5:]
    }

@app.get("/health")
async def health():
    return {"status": "online", "role": "telemetry-aggregator"}
