import asyncpg
from fastapi import HTTPException, status
from neo4j import AsyncDriver

from app.models.users import (
    PrivateUserProfile,
    PublicUserProfile,
    UserProfileUpdate,
    UserRecord,
)
from app.repositories.user_neo_repository import UserNeoRepository
from app.repositories.user_psql_repository import UserPsqlRepository


class UserService:
    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        neo4j_driver: AsyncDriver,
        user_psql_repository: UserPsqlRepository,
        user_neo_repository: UserNeoRepository,
    ):
        self.pg_pool = pg_pool
        self.neo4j_driver = neo4j_driver
        self.user_psql_repository = user_psql_repository
        self.user_neo_repository = user_neo_repository

    @staticmethod
    def _not_found() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    @staticmethod
    def _to_public_profile(user: UserRecord) -> PublicUserProfile:
        return PublicUserProfile(
            id=user.id,
            username=user.username,
            avatarUrl=user.avatar_url,
            bio=user.bio,
        )

    @staticmethod
    def _to_private_profile(user: UserRecord) -> PrivateUserProfile:
        return PrivateUserProfile(
            id=user.id,
            username=user.username,
            email=user.email,
            avatarUrl=user.avatar_url,
            bio=user.bio,
        )

    async def get_private_profile(self, user_id: str) -> PrivateUserProfile:
        async with self.pg_pool.acquire() as conn:
            user = await self.user_psql_repository.select_by_id(conn, user_id)

        if user is None:
            raise self._not_found()
        return self._to_private_profile(user)

    async def get_public_profile(self, user_id: str) -> PublicUserProfile:
        async with self.pg_pool.acquire() as conn:
            user = await self.user_psql_repository.select_by_id(conn, user_id)

        if user is None:
            raise self._not_found()
        return self._to_public_profile(user)

    async def update_profile(
        self,
        user_id: str,
        payload: UserProfileUpdate,
    ) -> PrivateUserProfile:
        updates = {}
        if "avatarUrl" in payload.model_fields_set:
            updates["avatar_url"] = (
                str(payload.avatarUrl) if payload.avatarUrl is not None else None
            )
        if "bio" in payload.model_fields_set:
            updates["bio"] = payload.bio

        async with self.pg_pool.acquire() as conn:
            user = await self.user_psql_repository.update_profile(
                conn,
                user_id,
                updates,
            )

        if user is None:
            raise self._not_found()
        return self._to_private_profile(user)

    async def delete_user(self, user_id: str) -> None:
        async with self.pg_pool.acquire() as conn:
            async with conn.transaction():
                user = await self.user_psql_repository.select_by_id(conn, user_id)
                if user is None:
                    raise self._not_found()

                deleted = await self.user_psql_repository.delete(conn, user_id)
                if not deleted:
                    raise self._not_found()

                async with self.neo4j_driver.session() as session:
                    transaction = await session.begin_transaction()
                    try:
                        await self.user_neo_repository.delete_by_psql_id(
                            transaction,
                            user_id,
                        )
                        await transaction.commit()
                    except Exception:
                        await transaction.rollback()
                        raise
