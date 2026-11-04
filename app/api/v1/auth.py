import asyncpg
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
import jwt

from app.schemas.auth import (
    AuthRegisterRequest, AuthLoginRequest, AuthTokenResponse,
    UserIdentity, RefreshRequest, RefreshResponse, LogoutResponse
)
from app.dependencies import get_pg_pool, get_neo4j_driver, get_current_user
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    hash_refresh_token
)

router = APIRouter()

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthTokenResponse,
    responses={409: {"description": "Conflict"}, 422: {"description": "Unprocessable Entity"}}
)
async def register(
    payload: AuthRegisterRequest,
    response: Response,
    pg_pool = Depends(get_pg_pool),
    neo4j_driver = Depends(get_neo4j_driver)
):
    user_id = f"usr_{uuid4().hex[:12]}"
    hashed_pw = hash_password(payload.password)

    # Generate tokens
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})
    hashed_refresh = hash_refresh_token(refresh_token)

    try:
        async with pg_pool.acquire() as conn:
            async with conn.transaction():
                # 1. Create user
                await conn.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash)
                    VALUES ($1, $2, $3, $4)
                    """,
                    user_id, payload.username, payload.email, hashed_pw
                )
                
                # 2. Store hashed refresh token
                await conn.execute(
                    """
                    INSERT INTO refresh_tokens (user_id, token_hash)
                    VALUES ($1, $2)
                    """,
                    user_id, hashed_refresh
                )

                # 3. Create node in Neo4j
                with neo4j_driver.session() as session:
                    session.run(
                        "CREATE (u:User {psqlId: $psql_id})",
                        psql_id=user_id
                    )

    except asyncpg.exceptions.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )

    # Set HTTP-only cookie for the refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True, # Ensure you are using HTTPS
        samesite="lax"
    )

    identity = UserIdentity(id=user_id, username=payload.username, email=payload.email)
    return AuthTokenResponse(user=identity, accessToken=access_token)


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    payload: AuthLoginRequest,
    response: Response,
    pg_pool = Depends(get_pg_pool)
):
    async with pg_pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT id, username, email, password_hash FROM users WHERE email = $1",
            payload.email
        )

        if not record or not verify_password(payload.password, record["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        user_id = record["id"]
        
        # Generate Tokens
        access_token = create_access_token({"sub": user_id})
        refresh_token = create_refresh_token({"sub": user_id})
        hashed_refresh = hash_refresh_token(refresh_token)

        # Store hashed refresh token in DB
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash)
            VALUES ($1, $2)
            """,
            user_id, hashed_refresh
        )

    # Set HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax"
    )

    identity = UserIdentity(id=user_id, username=record["username"], email=record["email"])
    return AuthTokenResponse(user=identity, accessToken=access_token)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    payload: RefreshRequest, # Keeping this if you still want fallback payload support
    pg_pool = Depends(get_pg_pool)
):
    # Try to get token from cookie first, fallback to payload
    token = request.cookies.get("refresh_token") or payload.refreshToken

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token"
        )

    try:
        token_data = decode_token(token)
        user_id = token_data.get("sub")
        token_type = token_data.get("type")

        if not user_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
            
        hashed_refresh = hash_refresh_token(token)

        # Verify the token hash exists in the database
        async with pg_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM refresh_tokens WHERE user_id = $1 AND token_hash = $2",
                user_id, hashed_refresh
            )
            
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has been revoked or is invalid"
                )

        # Issue a new access token
        new_access_token = create_access_token({"sub": user_id})
        return RefreshResponse(accessToken=new_access_token)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token format"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: UserIdentity = Depends(get_current_user),
    pg_pool = Depends(get_pg_pool)
):
    # Extract the current refresh token from cookies
    refresh_token = request.cookies.get("refresh_token")
    
    if refresh_token:
        hashed_refresh = hash_refresh_token(refresh_token)
        
        # Revoke it in the database
        async with pg_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM refresh_tokens WHERE user_id = $1 AND token_hash = $2",
                current_user.id, hashed_refresh
            )

    # Delete the cookie regardless
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )

    return LogoutResponse(message="Session terminated successfully")


@router.get("/me", response_model=UserIdentity)
async def get_me(current_user: UserIdentity = Depends(get_current_user)):
    return current_user
