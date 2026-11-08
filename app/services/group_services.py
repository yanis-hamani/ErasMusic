from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

import asyncpg
from fastapi import HTTPException, status
from neo4j import AsyncDriver
from neo4j.exceptions import ConstraintError

from app.models.common import Pagination
from app.models.groups import (
    Group,
    GroupCreate,
    GroupMember,
    GroupMemberCreate,
    GroupTagsReplace,
    GroupUpdate,
    PaginatedGroupMembersResponse,
    PaginatedGroupsResponse,
)
from app.repositories.chat_psql_repository import ChatPsqlRepository
from app.repositories.group_neo_repository import GroupNeoRepository


class GroupService:
    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        neo4j_driver: AsyncDriver,
        group_neo_repository: GroupNeoRepository,
        chat_psql_repository: ChatPsqlRepository,
    ):
        self.pg_pool = pg_pool
        self.neo4j_driver = neo4j_driver
        self.group_neo_repository = group_neo_repository
        self.chat_psql_repository = chat_psql_repository

    @staticmethod
    def _not_found(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    @staticmethod
    def _forbidden(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    @staticmethod
    def _conflict(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    @staticmethod
    def _pagination(page: int, limit: int, total: int) -> Pagination:
        return Pagination(
            page=page,
            limit=limit,
            totalItems=total,
            totalPages=ceil(total / limit) if total else 0,
        )

    async def _resolve_tags(self, transaction, tag_inputs):
        tags = []
        for tag_input in tag_inputs:
            if tag_input.type == "artist":
                tag = await self.group_neo_repository.select_artist_tag(
                    transaction,
                    tag_input.artistId,
                )
                if tag is None:
                    raise self._not_found(f"Artist {tag_input.artistId} not found")
            else:
                tag = await self.group_neo_repository.select_genre_tag(
                    transaction,
                    tag_input.genreId,
                )
                if tag is None:
                    raise self._not_found(f"Genre {tag_input.genreId} not found")
            tags.append(tag)
        return tags

    async def _to_group(self, transaction, record) -> Group:
        tags = await self.group_neo_repository.list_tags(transaction, record.id)
        return Group(
            id=record.id,
            ownerId=record.owner_id,
            name=record.name,
            description=record.description,
            tags=tags,
        )

    async def list_groups(self, page: int, limit: int) -> PaginatedGroupsResponse:
        async def read(transaction):
            total = await self.group_neo_repository.count_groups(transaction)
            records = await self.group_neo_repository.list_group_records(
                transaction,
                skip=(page - 1) * limit,
                limit=limit,
            )
            groups = [await self._to_group(transaction, record) for record in records]
            return PaginatedGroupsResponse(
                groups=groups,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def get_group(self, group_id: str) -> Group:
        async def read(transaction):
            record = await self.group_neo_repository.select_group(transaction, group_id)
            if record is None:
                raise self._not_found("Group not found")
            return await self._to_group(transaction, record)

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def create_group(self, owner_id: str, payload: GroupCreate) -> Group:
        group_id = f"grp_{uuid4().hex[:12]}"
        chat_id = f"chat_{uuid4().hex[:12]}"
        joined_at = datetime.now(timezone.utc)

        async def create_in_neo4j(transaction):
            if not await self.group_neo_repository.user_exists(transaction, owner_id):
                raise self._not_found("User not found")
            tags = await self._resolve_tags(transaction, payload.tags)
            record = await self.group_neo_repository.create_group(
                transaction,
                group_id=group_id,
                chat_id=chat_id,
                owner_id=owner_id,
                name=payload.name,
                description=payload.description,
                joined_at=joined_at,
            )
            await self.group_neo_repository.replace_tags(transaction, group_id, tags)
            return await self._to_group(transaction, record)

        try:
            async with self.pg_pool.acquire() as conn:
                async with conn.transaction():
                    await self.chat_psql_repository.create_group_chat(
                        conn,
                        chat_id,
                        owner_id,
                    )
                    async with self.neo4j_driver.session() as session:
                        return await session.execute_write(create_in_neo4j)
        except asyncpg.ForeignKeyViolationError as error:
            raise self._not_found("User not found") from error
        except (asyncpg.UniqueViolationError, ConstraintError) as error:
            raise self._conflict("Group or chat identifier already exists") from error

    async def update_group(
        self,
        owner_id: str,
        group_id: str,
        payload: GroupUpdate,
    ) -> Group:
        async def write(transaction):
            record = await self.group_neo_repository.select_group(transaction, group_id)
            if record is None:
                raise self._not_found("Group not found")
            if record.owner_id != owner_id:
                raise self._forbidden("Only the group owner can update this group")
            updates = {
                field: getattr(payload, field)
                for field in payload.model_fields_set
            }
            updated = await self.group_neo_repository.update_group(
                transaction,
                group_id,
                updates,
            )
            return await self._to_group(transaction, updated)

        async with self.neo4j_driver.session() as session:
            return await session.execute_write(write)

    async def delete_group(self, owner_id: str, group_id: str) -> None:
        async def read(transaction):
            record = await self.group_neo_repository.select_group(transaction, group_id)
            if record is None:
                raise self._not_found("Group not found")
            if record.owner_id != owner_id:
                raise self._forbidden("Only the group owner can delete this group")
            return record

        async with self.neo4j_driver.session() as session:
            record = await session.execute_read(read)

        async def delete_in_neo4j(transaction):
            current = await self.group_neo_repository.select_group(transaction, group_id)
            if current is None:
                raise self._not_found("Group not found")
            if current.owner_id != owner_id:
                raise self._forbidden("Only the group owner can delete this group")
            if not await self.group_neo_repository.delete_group(transaction, group_id):
                raise self._not_found("Group not found")

        async with self.pg_pool.acquire() as conn:
            async with conn.transaction():
                if not await self.chat_psql_repository.delete_chat(conn, record.psql_chat_id):
                    raise self._not_found("Linked group chat not found")
                async with self.neo4j_driver.session() as session:
                    await session.execute_write(delete_in_neo4j)

    async def list_members(
        self,
        group_id: str,
        page: int,
        limit: int,
    ) -> PaginatedGroupMembersResponse:
        async def read(transaction):
            if await self.group_neo_repository.select_group(transaction, group_id) is None:
                raise self._not_found("Group not found")
            total = await self.group_neo_repository.count_members(transaction, group_id)
            members = await self.group_neo_repository.list_members(
                transaction,
                group_id,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedGroupMembersResponse(
                members=members,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def add_member(
        self,
        current_user_id: str,
        group_id: str,
        payload: GroupMemberCreate | None,
    ) -> GroupMember:
        target_user_id = payload.userId if payload and payload.userId else current_user_id

        async def preflight(transaction):
            record = await self.group_neo_repository.select_group(transaction, group_id)
            if record is None:
                raise self._not_found("Group not found")
            if target_user_id != current_user_id and record.owner_id != current_user_id:
                raise self._forbidden("Only the group owner can add another user")
            if not await self.group_neo_repository.user_exists(transaction, target_user_id):
                raise self._not_found("Target user not found")
            if await self.group_neo_repository.membership_exists(
                transaction,
                group_id,
                target_user_id,
            ):
                raise self._conflict("User is already a group member")
            return record

        async with self.neo4j_driver.session() as session:
            record = await session.execute_read(preflight)

        joined_at = datetime.now(timezone.utc)

        async def create_in_neo4j(transaction):
            current = await self.group_neo_repository.select_group(transaction, group_id)
            if current is None:
                raise self._not_found("Group not found")
            if target_user_id != current_user_id and current.owner_id != current_user_id:
                raise self._forbidden("Only the group owner can add another user")
            if await self.group_neo_repository.membership_exists(
                transaction,
                group_id,
                target_user_id,
            ):
                raise self._conflict("User is already a group member")
            return await self.group_neo_repository.create_membership(
                transaction,
                group_id,
                target_user_id,
                joined_at,
            )

        try:
            async with self.pg_pool.acquire() as conn:
                async with conn.transaction():
                    await self.chat_psql_repository.add_participant(
                        conn,
                        record.psql_chat_id,
                        target_user_id,
                    )
                    async with self.neo4j_driver.session() as session:
                        return await session.execute_write(create_in_neo4j)
        except asyncpg.ForeignKeyViolationError as error:
            raise self._not_found("User or linked group chat not found") from error
        except asyncpg.UniqueViolationError as error:
            raise self._conflict("User is already a group member") from error

    async def leave_group(self, user_id: str, group_id: str) -> None:
        async def preflight(transaction):
            record = await self.group_neo_repository.select_group(transaction, group_id)
            if record is None:
                raise self._not_found("Group not found")
            if record.owner_id == user_id:
                raise self._conflict("The group owner cannot leave the group")
            member = await self.group_neo_repository.select_member(
                transaction,
                group_id,
                user_id,
            )
            if member is None:
                raise self._not_found("Group membership not found")
            return record

        async with self.neo4j_driver.session() as session:
            record = await session.execute_read(preflight)

        async def delete_in_neo4j(transaction):
            current = await self.group_neo_repository.select_group(transaction, group_id)
            if current is None:
                raise self._not_found("Group not found")
            if current.owner_id == user_id:
                raise self._conflict("The group owner cannot leave the group")
            member = await self.group_neo_repository.select_member(
                transaction,
                group_id,
                user_id,
            )
            if member is None:
                raise self._not_found("Group membership not found")
            if not await self.group_neo_repository.delete_membership(
                transaction,
                group_id,
                user_id,
            ):
                raise self._not_found("Group membership not found")

        async with self.pg_pool.acquire() as conn:
            async with conn.transaction():
                if not await self.chat_psql_repository.remove_participant(
                    conn,
                    record.psql_chat_id,
                    user_id,
                ):
                    raise self._not_found("Chat participation not found")
                async with self.neo4j_driver.session() as session:
                    await session.execute_write(delete_in_neo4j)

    async def list_tags(self, group_id: str):
        async def read(transaction):
            if await self.group_neo_repository.select_group(transaction, group_id) is None:
                raise self._not_found("Group not found")
            return await self.group_neo_repository.list_tags(transaction, group_id)

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def replace_tags(
        self,
        owner_id: str,
        group_id: str,
        payload: GroupTagsReplace,
    ):
        async def write(transaction):
            record = await self.group_neo_repository.select_group(transaction, group_id)
            if record is None:
                raise self._not_found("Group not found")
            if record.owner_id != owner_id:
                raise self._forbidden("Only the group owner can replace tags")
            tags = await self._resolve_tags(transaction, payload.tags)
            await self.group_neo_repository.replace_tags(transaction, group_id, tags)
            return tags

        async with self.neo4j_driver.session() as session:
            return await session.execute_write(write)
