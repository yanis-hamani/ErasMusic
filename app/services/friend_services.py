from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

from fastapi import HTTPException, status
from neo4j import AsyncDriver
from neo4j.exceptions import ConstraintError

from app.models.common import Pagination
from app.models.friends import (
    FriendRequest,
    FriendRequestCreate,
    FriendRequestDirection,
    FriendRequestStatusEnum,
    FriendshipStatus,
    FriendshipStatusEnum,
    PaginatedFriendRequestsResponse,
    PaginatedFriendsResponse,
)
from app.repositories.friend_neo_repository import FriendNeoRepository


class FriendService:
    def __init__(
        self,
        neo4j_driver: AsyncDriver,
        friend_neo_repository: FriendNeoRepository,
    ):
        self.neo4j_driver = neo4j_driver
        self.friend_neo_repository = friend_neo_repository

    @staticmethod
    def _not_found(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

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

    @staticmethod
    def _pair_key(first_user_id: str, second_user_id: str) -> str:
        return ":".join(sorted((first_user_id, second_user_id)))

    async def list_friends(
        self,
        user_id: str,
        page: int,
        limit: int,
    ) -> PaginatedFriendsResponse:
        async def read(transaction):
            if not await self.friend_neo_repository.user_exists(transaction, user_id):
                raise self._not_found("User not found")
            total = await self.friend_neo_repository.count_friends(transaction, user_id)
            friends = await self.friend_neo_repository.list_friends(
                transaction,
                user_id,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedFriendsResponse(
                friends=friends,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def get_friendship_status(
        self,
        current_user_id: str,
        target_user_id: str,
    ) -> FriendshipStatus:
        async def read(transaction):
            if not await self.friend_neo_repository.user_exists(transaction, current_user_id):
                raise self._not_found("User not found")
            if not await self.friend_neo_repository.user_exists(transaction, target_user_id):
                raise self._not_found("Target user not found")

            friendship_status = FriendshipStatusEnum.none
            if current_user_id != target_user_id:
                friendship_status = await self.friend_neo_repository.get_friendship_status(
                    transaction,
                    current_user_id,
                    target_user_id,
                )
            return FriendshipStatus(userId=target_user_id, status=friendship_status)

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def remove_friend(self, current_user_id: str, target_user_id: str) -> None:
        async def write(transaction):
            if not await self.friend_neo_repository.user_exists(transaction, current_user_id):
                raise self._not_found("User not found")
            if not await self.friend_neo_repository.user_exists(transaction, target_user_id):
                raise self._not_found("Target user not found")
            deleted = await self.friend_neo_repository.delete_friendship(
                transaction,
                current_user_id,
                target_user_id,
            )
            if not deleted:
                raise self._not_found("Friendship not found")

        async with self.neo4j_driver.session() as session:
            await session.execute_write(write)

    async def create_friend_request(
        self,
        sender_id: str,
        payload: FriendRequestCreate,
    ) -> FriendRequest:
        target_user_id = payload.targetUserId
        if sender_id == target_user_id:
            raise self._conflict("You cannot send a friend request to yourself")

        request_id = f"req_{uuid4().hex[:12]}"
        pair_key = self._pair_key(sender_id, target_user_id)
        created_at = datetime.now(timezone.utc)

        async def write(transaction):
            if not await self.friend_neo_repository.user_exists(transaction, sender_id):
                raise self._not_found("User not found")
            if not await self.friend_neo_repository.user_exists(transaction, target_user_id):
                raise self._not_found("Target user not found")
            if await self.friend_neo_repository.friendship_exists(
                transaction,
                sender_id,
                target_user_id,
            ):
                raise self._conflict("Users are already friends")
            if await self.friend_neo_repository.pending_request_exists(
                transaction,
                sender_id,
                target_user_id,
            ):
                raise self._conflict("A friend request is already pending")
            return await self.friend_neo_repository.create_request(
                transaction,
                request_id=request_id,
                pair_key=pair_key,
                sender_id=sender_id,
                target_user_id=target_user_id,
                created_at=created_at,
            )

        try:
            async with self.neo4j_driver.session() as session:
                return await session.execute_write(write)
        except ConstraintError as error:
            raise self._conflict("A friend request is already pending") from error

    async def list_friend_requests(
        self,
        user_id: str,
        direction: FriendRequestDirection,
        page: int,
        limit: int,
    ) -> PaginatedFriendRequestsResponse:
        async def read(transaction):
            if not await self.friend_neo_repository.user_exists(transaction, user_id):
                raise self._not_found("User not found")
            total = await self.friend_neo_repository.count_requests(
                transaction,
                user_id,
                direction,
            )
            requests = await self.friend_neo_repository.list_requests(
                transaction,
                user_id,
                direction,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedFriendRequestsResponse(
                requests=requests,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def accept_friend_request(self, user_id: str, request_id: str) -> FriendRequest:
        async def write(transaction):
            request = await self.friend_neo_repository.select_request(transaction, request_id)
            if request is None:
                raise self._not_found("Friend request not found")
            if request.targetUserId != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the target user can accept this friend request",
                )
            if await self.friend_neo_repository.friendship_exists(
                transaction,
                request.senderId,
                request.targetUserId,
            ):
                raise self._conflict("Users are already friends")

            await self.friend_neo_repository.create_friendship(
                transaction,
                request.senderId,
                request.targetUserId,
            )
            deleted = await self.friend_neo_repository.delete_request(
                transaction,
                request.requestId,
            )
            if not deleted:
                raise self._conflict("Friend request was already processed")
            return request.model_copy(update={"status": FriendRequestStatusEnum.accepted})

        async with self.neo4j_driver.session() as session:
            return await session.execute_write(write)

    async def decline_friend_request(self, user_id: str, request_id: str) -> FriendRequest:
        async def write(transaction):
            request = await self.friend_neo_repository.select_request(transaction, request_id)
            if request is None:
                raise self._not_found("Friend request not found")
            if request.targetUserId != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the target user can decline this friend request",
                )
            deleted = await self.friend_neo_repository.delete_request(
                transaction,
                request.requestId,
            )
            if not deleted:
                raise self._conflict("Friend request was already processed")
            return request.model_copy(update={"status": FriendRequestStatusEnum.declined})

        async with self.neo4j_driver.session() as session:
            return await session.execute_write(write)
