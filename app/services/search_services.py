from math import ceil

import asyncpg
from fastapi import HTTPException, status
from neo4j import AsyncDriver

from app.models.common import Pagination
from app.models.groups import Group, PaginatedGroupsResponse
from app.models.search import PaginatedUsersResponse
from app.repositories.group_neo_repository import GroupNeoRepository
from app.repositories.user_psql_repository import UserPsqlRepository


class SearchService:
    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        neo4j_driver: AsyncDriver,
        user_psql_repository: UserPsqlRepository,
        group_neo_repository: GroupNeoRepository,
    ):
        self.pg_pool = pg_pool
        self.neo4j_driver = neo4j_driver
        self.user_psql_repository = user_psql_repository
        self.group_neo_repository = group_neo_repository

    @staticmethod
    def _normalize_query(query: str) -> str:
        normalized = query.strip().lower()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Search query must not be blank",
            )
        return normalized

    @staticmethod
    def _pagination(page: int, limit: int, total: int) -> Pagination:
        return Pagination(
            page=page,
            limit=limit,
            totalItems=total,
            totalPages=ceil(total / limit) if total else 0,
        )

    async def search_users(
        self,
        current_user_id: str,
        query: str,
        page: int,
        limit: int,
    ) -> PaginatedUsersResponse:
        normalized = self._normalize_query(query)
        async with self.pg_pool.acquire() as connection:
            total = await self.user_psql_repository.count_search_users(
                connection,
                current_user_id,
                normalized,
            )
            users = await self.user_psql_repository.search_users(
                connection,
                current_user_id,
                normalized,
                skip=(page - 1) * limit,
                limit=limit,
            )

        return PaginatedUsersResponse(
            users=users,
            pagination=self._pagination(page, limit, total),
        )

    async def search_groups(
        self,
        query: str,
        page: int,
        limit: int,
    ) -> PaginatedGroupsResponse:
        normalized = self._normalize_query(query)

        async def read(transaction):
            total = await self.group_neo_repository.count_search_groups(
                transaction,
                normalized,
            )
            records = await self.group_neo_repository.search_group_records(
                transaction,
                normalized,
                skip=(page - 1) * limit,
                limit=limit,
            )
            groups = []
            for record in records:
                tags = await self.group_neo_repository.list_tags(
                    transaction,
                    record.id,
                )
                groups.append(
                    Group(
                        id=record.id,
                        ownerId=record.owner_id,
                        name=record.name,
                        description=record.description,
                        tags=tags,
                    )
                )
            return PaginatedGroupsResponse(
                groups=groups,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)
