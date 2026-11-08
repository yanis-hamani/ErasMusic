from neo4j import AsyncDriver
from starlette.status import HTTP_404_NOT_FOUND
from app.repositories.user_psql_repository import UserPsqlRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.register_hashed_repository import RegisterHashedRepository
from app.repositories.user_neo_repository import UserNeoRepository
from app.models.auth import RegisterRequest, RegisterHashed, RefreshToken, UserNeo, UserIdentity, AuthTokenResponse, AuthLoginRequest, RefreshResponse
from app.core.security import hash_password, create_access_token, create_refresh_token, hash_refresh_token, verify_password, decode_token
import asyncpg
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
import jwt

class AuthService:

    def __init__(
            self,
            pg_pool: asyncpg.Pool,
            neo4j_driver: AsyncDriver,
            user_neo_repository: UserNeoRepository,
            user_psql_repository: UserPsqlRepository,
            register_hashed_repository: RegisterHashedRepository,
            refresh_token_repository: RefreshTokenRepository,
        ):
        self.pg_pool = pg_pool
        self.neo4j_driver = neo4j_driver
        self.user_neo_repository = user_neo_repository
        self.user_psql_repository = user_psql_repository
        self.register_hashed_repository = register_hashed_repository
        self.refresh_token_repository = refresh_token_repository

    def __create_tokens(self, user_id: str) -> tuple[str, RefreshToken, str]:
            access_token = create_access_token({"sub": user_id})
            refresh_token = create_refresh_token({"sub": user_id})
            hashed_refresh = hash_refresh_token(refresh_token)
            refresh_token_object = RefreshToken(
                user_id = user_id,
                hashed_token = hashed_refresh
            )
            return access_token, refresh_token_object, refresh_token

    async def register(self, payload: RegisterRequest) -> tuple[AuthTokenResponse, str]:
        user_id = f"usr_{uuid4().hex[:12]}"
        hashed_pw = hash_password(payload.password)
        access_token, refresh_token_object, refresh_token = self.__create_tokens(user_id)

        register_hashed = RegisterHashed(
            id = user_id,
            username = payload.username,
            email= payload.email,
            hashed_password = hashed_pw
        )
        user = UserNeo(
            psql_id = user_id,
            username = payload.username
        )

        # TODO: add early validation on top of the uniqueviolation error ?
        try:
            async with self.pg_pool.acquire() as conn:
                async with conn.transaction():
                    # ignore return value as it is the same ?
                    await self.register_hashed_repository.save(conn, register_hashed)
                    await self.refresh_token_repository.save(conn, refresh_token_object)

                    async with self.neo4j_driver.session() as session:
                        tx = await session.begin_transaction()
                        try:
                            await self.user_neo_repository.save(tx, user)
                            await tx.commit()
                        except Exception:
                            await tx.rollback()
                            raise

        except asyncpg.exceptions.UniqueViolationError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already exists"
            )

        identity = UserIdentity(id=user_id, username=payload.username, email=payload.email)
        return AuthTokenResponse(user=identity, accessToken=access_token), refresh_token


    async def login(self, payload: AuthLoginRequest) -> tuple[AuthTokenResponse, str]:
        async with self.pg_pool.acquire() as conn:
            register_hashed = await self.register_hashed_repository.select_by_email(conn, payload.email)

            if register_hashed is None or not verify_password(payload.password, register_hashed.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )

            user_id = register_hashed.id
            access_token, refresh_token_object, refresh_token = self.__create_tokens(user_id)
            await self.refresh_token_repository.save(conn, refresh_token_object)

        identity = UserIdentity(id=user_id, username=register_hashed.username, email=register_hashed.email)
        return AuthTokenResponse(user=identity, accessToken=access_token), refresh_token


    async def refresh(self, refresh_token: str) -> RefreshResponse:
        try:
            token_data = decode_token(refresh_token)
            user_id = token_data.get("sub")
            token_type = token_data.get("type")

            if not user_id or token_type != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )

            hashed_refresh = hash_refresh_token(refresh_token)
            refresh_token_object = RefreshToken(user_id=user_id, hashed_token=hashed_refresh)

            async with self.pg_pool.acquire() as conn:
                exists = await self.refresh_token_repository.exists(conn, refresh_token_object)
                if not exists:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Refresh token has been revoked or is invalid"
                    )

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

    async def delete_refresh_token(self, refresh_token: str, user_id: str) -> None:
        hashed_refresh = hash_refresh_token(refresh_token)

        async with self.pg_pool.acquire() as conn:
            current_user = await self.user_psql_repository.select_by_id(conn, user_id)
            if current_user is None:
                raise HTTPException(
                    status_code=HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            refresh_token_object = RefreshToken(user_id=current_user.id, hashed_token=hashed_refresh)
            await self.refresh_token_repository.delete(conn, refresh_token_object)

