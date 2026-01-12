@echo off
echo Starting Flowguard Development Environment...

REM Start Backend
start cmd /k "cd backend && python -m venv .venv && .\.venv\Scripts\activate && pip install -r requirements.txt && uvicorn src.main:app --reload"

REM Start Frontend
start cmd /k "cd frontend && npm install && npm run dev"

echo Services started in new windows.
