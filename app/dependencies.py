from fastapi import Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt

from app.schemas.auth import UserIdentity
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")

async def get_pg_pool(request: Request):
    return request.app.state.pg_pool

async def get_neo4j_driver(request: Request):
    return request.app.state.neo4j_driver

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    pg_pool = Depends(get_pg_pool)
) -> UserIdentity:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise credentials_exception
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    async with pg_pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT id, username, email FROM users WHERE id = $1", user_id
        )
        
    if not record:
        raise credentials_exception
        
    return UserIdentity(**dict(record))
