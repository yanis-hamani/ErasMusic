from fastapi import APIRouter, HTTPException
from dishka.integrations.fastapi import inject, FromDishka
from asyncpg import Pool
from neo4j import AsyncDriver

router = APIRouter()

@router.get("/health", tags=["System"])
@inject
async def health(
    pg_pool: FromDishka[Pool],
    neo4j_driver: FromDishka[AsyncDriver]
):
    try:
        # Use the injected driver directly
        await neo4j_driver.verify_connectivity()
        
        # Use the injected pool directly
        async with pg_pool.acquire() as connection:
            await connection.fetchval('SELECT 1')
            
        return {
            "status": "ok",
            "databases": {
                "neo4j": "connected",
                "postgres": "connected"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")
