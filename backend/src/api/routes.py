from fastapi import APIRouter

api_router = APIRouter()

@api_router.get("/workflows")
async def list_workflows():
    # Mock response for now
    return [
        {"id": "wf_1", "name": "Document Extraction", "status": "active"},
        {"id": "wf_2", "name": "Code Review Agent", "status": "draft"},
    ]
