from fastapi import FastAPI
from app.core.database import lifespan
from app.api.v1.router import api_router
from app.api.health import router as health_router

app = FastAPI(
    title="ErasMusic API",
    description="Neo4j & PostgreSQL API for ErasMusic",
    version="1.0.0",
    lifespan=lifespan
)

# Root-level routes (like /health)
app.include_router(health_router)

# Versioned API routes (like /v1/auth/register)
app.include_router(api_router)
