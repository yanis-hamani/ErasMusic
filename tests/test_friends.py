import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from neo4j.exceptions import ConstraintError
from neo4j.time import DateTime

from app.models.friends import (
    FriendRequest,
    FriendRequestCreate,
    FriendRequestDirection,
    FriendRequestStatusEnum,
    FriendSummary,
    FriendshipStatusEnum,
)
from app.services.friend_services import FriendService
from app.repositories.friend_neo_repository import FriendNeoRepository


class FakeSession:
    def __init__(self):
        self.transaction = object()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute_read(self, callback):
        return await callback(self.transaction)

    async def execute_write(self, callback):
        return await callback(self.transaction)


class FakeDriver:
    def session(self):
        return FakeSession()


class FakeFriendRepository:
    def __init__(self):
        self.users = {"usr_current", "usr_target", "usr_sender"}
        self.friends = [FriendSummary(id="usr_target", username="Target")]
        self.friend_count = 1
        self.friendship = False
        self.friendship_status = FriendshipStatusEnum.none
        self.friendship_deleted = True
        self.pending_request = None
        self.requests = []
        self.request_count = 0
        self.selected_request = None
        self.request_deleted = True
        self.created_request = None
        self.created_friendship = None
        self.create_request_error = None
        self.last_request_page = None

    async def user_exists(self, transaction, user_id):
        return user_id in self.users

    async def count_friends(self, transaction, user_id):
        return self.friend_count

    async def list_friends(self, transaction, user_id, skip, limit):
        return self.friends

    async def friendship_exists(self, transaction, first_user_id, second_user_id):
        return self.friendship

    async def get_friendship_status(self, transaction, current_user_id, target_user_id):
        return self.friendship_status

    async def delete_friendship(self, transaction, current_user_id, target_user_id):
        return self.friendship_deleted

    async def pending_request_exists(
        self,
        transaction,
        first_user_id,
        second_user_id,
    ):
        return self.pending_request is not None

    async def create_request(
        self,
        transaction,
        request_id,
        pair_key,
        sender_id,
        target_user_id,
        created_at,
    ):
        if self.create_request_error is not None:
            raise self.create_request_error
        self.created_request = FriendRequest(
            requestId=request_id,
            senderId=sender_id,
            targetUserId=target_user_id,
            status=FriendRequestStatusEnum.pending,
            createdAt=created_at,
        )
        return self.created_request

    async def count_requests(self, transaction, user_id, direction):
        return self.request_count

    async def list_requests(self, transaction, user_id, direction, skip, limit):
        self.last_request_page = (direction, skip, limit)
        return self.requests

    async def select_request(self, transaction, request_id):
        return self.selected_request

    async def create_friendship(self, transaction, first_user_id, second_user_id):
        self.created_friendship = (first_user_id, second_user_id)

    async def delete_request(self, transaction, request_id):
        return self.request_deleted


def pending_request(
    sender_id="usr_sender",
    target_user_id="usr_current",
):
    return FriendRequest(
        requestId="req_123",
        senderId=sender_id,
        targetUserId=target_user_id,
        status=FriendRequestStatusEnum.pending,
        createdAt=datetime.now(timezone.utc),
    )


class FriendServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeFriendRepository()
        self.service = FriendService(FakeDriver(), self.repository)

    async def test_list_friends_builds_pagination(self):
        response = await self.service.list_friends("usr_current", page=2, limit=1)

        self.assertEqual(response.friends, self.repository.friends)
        self.assertEqual(response.pagination.page, 2)
        self.assertEqual(response.pagination.totalItems, 1)
        self.assertEqual(response.pagination.totalPages, 1)

    async def test_friendship_status_supports_incoming_requests(self):
        self.repository.friendship_status = FriendshipStatusEnum.pending_incoming

        response = await self.service.get_friendship_status(
            "usr_current",
            "usr_target",
        )

        self.assertEqual(response.status, FriendshipStatusEnum.pending_incoming)

    async def test_friendship_status_with_self_is_none(self):
        response = await self.service.get_friendship_status(
            "usr_current",
            "usr_current",
        )

        self.assertEqual(response.status, FriendshipStatusEnum.none)

    async def test_remove_missing_friendship_returns_404(self):
        self.repository.friendship_deleted = False

        with self.assertRaises(HTTPException) as raised:
            await self.service.remove_friend("usr_current", "usr_target")

        self.assertEqual(raised.exception.status_code, 404)
    async def test_self_request_returns_409(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.create_friend_request(
                "usr_current",
                FriendRequestCreate(targetUserId="usr_current"),
            )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_missing_request_target_returns_404(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.create_friend_request(
                "usr_current",
                FriendRequestCreate(targetUserId="usr_missing"),
            )

        self.assertEqual(raised.exception.status_code, 404)

    async def test_existing_friendship_returns_409(self):
        self.repository.friendship = True

        with self.assertRaises(HTTPException) as raised:
            await self.service.create_friend_request(
                "usr_current",
                FriendRequestCreate(targetUserId="usr_target"),
            )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_crossed_request_returns_409(self):
        self.repository.pending_request = pending_request(
            sender_id="usr_target",
            target_user_id="usr_current",
        )

        with self.assertRaises(HTTPException) as raised:
            await self.service.create_friend_request(
                "usr_current",
                FriendRequestCreate(targetUserId="usr_target"),
            )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_constraint_race_returns_409(self):
        self.repository.create_request_error = ConstraintError("duplicate pair")

        with self.assertRaises(HTTPException) as raised:
            await self.service.create_friend_request(
                "usr_current",
                FriendRequestCreate(targetUserId="usr_target"),
            )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_request_listing_is_paginated(self):
        self.repository.requests = [pending_request()]
        self.repository.request_count = 21

        response = await self.service.list_friend_requests(
            "usr_current",
            FriendRequestDirection.incoming,
            page=2,
            limit=10,
        )

        self.assertEqual(response.pagination.totalPages, 3)
        self.assertEqual(
            self.repository.last_request_page,
            (FriendRequestDirection.incoming, 10, 10),
        )

    async def test_only_target_can_accept_request(self):
        self.repository.selected_request = pending_request()

        with self.assertRaises(HTTPException) as raised:
            await self.service.accept_friend_request("usr_sender", "req_123")

        self.assertEqual(raised.exception.status_code, 403)

    async def test_accept_creates_friendship_and_deletes_request(self):
        self.repository.selected_request = pending_request()

        response = await self.service.accept_friend_request("usr_current", "req_123")

        self.assertEqual(response.status, FriendRequestStatusEnum.accepted)
        self.assertEqual(
            self.repository.created_friendship,
            ("usr_sender", "usr_current"),
        )

    async def test_decline_deletes_request(self):
        self.repository.selected_request = pending_request()

        response = await self.service.decline_friend_request("usr_current", "req_123")

        self.assertEqual(response.status, FriendRequestStatusEnum.declined)

    async def test_processed_request_returns_404(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.accept_friend_request("usr_current", "req_missing")

        self.assertEqual(raised.exception.status_code, 404)


class FriendRepositoryMappingTests(unittest.TestCase):
    def test_neo4j_datetime_is_converted_to_native_datetime(self):
        request = FriendNeoRepository._request_from_record(
            {
                "requestId": "req_123",
                "senderId": "usr_sender",
                "targetUserId": "usr_target",
                "status": "pending",
                "createdAt": DateTime.now(),
            }
        )

        self.assertIsInstance(request.createdAt, datetime)


if __name__ == "__main__":
    unittest.main()
