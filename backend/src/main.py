from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api import routes

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Flowguard AI Workflow Orchestration Platform",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routes
app.include_router(routes.api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Welcome to Flowguard Control Plane",
        "docs": "/docs",
        "version": settings.VERSION
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "flowguard-backend"}
