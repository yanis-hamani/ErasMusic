from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.get("/health", tags=["System"])
async def health(request: Request):
    try:
        request.app.state.neo4j_driver.verify_connectivity()
        
        async with request.app.state.pg_pool.acquire() as connection:
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
