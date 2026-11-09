import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError

from app.models.chats import (
    Chat,
    ChatMemberCreate,
    ChatMessage,
    ChatType,
    CreateDirectChat,
    CreateGroupChat,
    LockedChat,
    SendMessage,
)
from app.repositories.chat_psql_repository import ChatPsqlRepository
from app.repositories.friend_neo_repository import FriendNeoRepository
from app.services.chat_services import ChatService


class AsyncContext:
    def __init__(self, value):
        self.value = value
        self.rolled_back = False

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        self.rolled_back = exc_type is not None
        return False


class FakeConnection:
    def __init__(self):
        self.transactions = []

    def transaction(self):
        context = AsyncContext(self)
        self.transactions.append(context)
        return context


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return AsyncContext(self.connection)


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
        self.are_friends = True
        self.increase_result = True
        self.increase_error = None
        self.increases = []

    async def friendship_exists(self, transaction, first_user_id, second_user_id):
        return self.are_friends

    async def increase_closeness(
        self,
        transaction,
        first_user_id,
        second_user_id,
        interaction_at,
    ):
        if self.increase_error is not None:
            raise self.increase_error
        self.increases.append((first_user_id, second_user_id, interaction_at))
        return self.increase_result


class FakeGroupRepository:
    def __init__(self):
        self.linked_chat_ids = set()

    async def group_chat_exists(self, transaction, chat_id):
        return chat_id in self.linked_chat_ids


class FakeChatRepository:
    def __init__(self):
        self.users = {"usr_current", "usr_friend", "usr_other"}
        self.chats = {
            "chat_direct": Chat(
                id="chat_direct",
                type=ChatType.direct,
                participantIds=["usr_current", "usr_friend"],
            ),
            "chat_group": Chat(
                id="chat_group",
                type=ChatType.group,
                participantIds=["usr_current", "usr_friend"],
            ),
        }
        self.last_activity_dates = {}
        self.messages = []
        self.other_messaged_today = False
        self.existing_direct_chat_id = None
        self.pair_locks = []
        self.created_chat = None
        self.marked_activity = None
        self.deleted_chat = None
        self.last_message_page = None

    async def count_user_chats(self, connection, user_id):
        return sum(user_id in chat.participantIds for chat in self.chats.values())

    async def list_user_chats(self, connection, user_id, skip, limit):
        chats = [
            chat for chat in self.chats.values() if user_id in chat.participantIds
        ]
        return chats[skip : skip + limit]

    async def select_chat(self, connection, chat_id):
        return self.chats.get(chat_id)

    async def lock_chat(self, connection, chat_id):
        chat = self.chats.get(chat_id)
        if chat is None:
            return None
        return LockedChat(
            chat=chat,
            last_closeness_activity_date=self.last_activity_dates.get(chat_id),
        )

    async def users_exist(self, connection, user_ids):
        return set(user_ids) <= self.users

    async def acquire_direct_pair_lock(self, connection, pair_key):
        self.pair_locks.append(pair_key)

    async def find_direct_chat(self, connection, participant_ids):
        return self.existing_direct_chat_id

    async def create_chat(
        self,
        connection,
        chat_id,
        chat_type,
        participant_ids,
    ):
        chat = Chat(
            id=chat_id,
            type=chat_type,
            participantIds=participant_ids,
        )
        self.chats[chat_id] = chat
        self.created_chat = chat
        return chat

    async def count_messages(self, connection, chat_id):
        return len([message for message in self.messages if message.chatId == chat_id])

    async def list_messages(self, connection, chat_id, skip, limit):
        self.last_message_page = (chat_id, skip, limit)
        messages = [message for message in self.messages if message.chatId == chat_id]
        return messages[skip : skip + limit]

    async def other_participant_messaged_on_date(
        self,
        connection,
        chat_id,
        sender_id,
        activity_date,
    ):
        return self.other_messaged_today

    async def create_message(
        self,
        connection,
        message_id,
        chat_id,
        sender_id,
        message,
        created_at,
    ):
        created = ChatMessage(
            id=message_id,
            chatId=chat_id,
            senderId=sender_id,
            message=message,
            createdAt=created_at,
        )
        self.messages.append(created)
        return created

    async def mark_closeness_activity(self, connection, chat_id, activity_date):
        self.last_activity_dates[chat_id] = activity_date
        self.marked_activity = (chat_id, activity_date)

    async def add_participant(self, connection, chat_id, user_id):
        self.chats[chat_id].participantIds.append(user_id)

    async def remove_participant(self, connection, chat_id, user_id):
        chat = self.chats[chat_id]
        if user_id not in chat.participantIds:
            return False
        chat.participantIds.remove(user_id)
        return True

    async def count_participants(self, connection, chat_id):
        return len(self.chats[chat_id].participantIds)

    async def delete_chat(self, connection, chat_id):
        self.deleted_chat = chat_id
        return self.chats.pop(chat_id, None) is not None


class ChatModelTests(unittest.TestCase):
    def test_direct_chat_requires_exactly_one_other_participant(self):
        with self.assertRaises(ValidationError):
            CreateDirectChat(type="direct", participantIds=[])
        with self.assertRaises(ValidationError):
            CreateDirectChat(
                type="direct",
                participantIds=["usr_one", "usr_two"],
            )

    def test_group_chat_rejects_duplicate_participants(self):
        with self.assertRaises(ValidationError):
            CreateGroupChat(
                type="group",
                participantIds=["usr_one", "usr_one"],
            )

    def test_message_validation_rejects_blank_and_oversized_text(self):
        with self.assertRaises(ValidationError):
            SendMessage(message="   ")
        with self.assertRaises(ValidationError):
            SendMessage(message="a" * 4001)


class ChatServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.chat_repository = FakeChatRepository()
        self.friend_repository = FakeFriendRepository()
        self.group_repository = FakeGroupRepository()
        self.service = ChatService(
            pg_pool=FakePool(self.connection),
            neo4j_driver=FakeDriver(),
            chat_psql_repository=self.chat_repository,
            friend_neo_repository=self.friend_repository,
            group_neo_repository=self.group_repository,
        )

    async def test_chat_listing_is_paginated(self):
        response = await self.service.list_chats(
            "usr_current",
            page=2,
            limit=1,
        )

        self.assertEqual(len(response.chats), 1)
        self.assertEqual(response.pagination.page, 2)
        self.assertEqual(response.pagination.totalItems, 2)
        self.assertEqual(response.pagination.totalPages, 2)

    async def test_direct_chat_creation_requires_friendship_and_locks_pair(self):
        chat = await self.service.create_chat(
            "usr_current",
            CreateDirectChat(type="direct", participantIds=["usr_friend"]),
        )

        self.assertEqual(chat.type, ChatType.direct)
        self.assertEqual(chat.participantIds, ["usr_current", "usr_friend"])
        self.assertEqual(self.chat_repository.pair_locks, ["usr_current:usr_friend"])

    async def test_non_friend_direct_chat_returns_403(self):
        self.friend_repository.are_friends = False

        with self.assertRaises(HTTPException) as raised:
            await self.service.create_chat(
                "usr_current",
                CreateDirectChat(type="direct", participantIds=["usr_other"]),
            )

        self.assertEqual(raised.exception.status_code, 403)

    async def test_duplicate_direct_chat_returns_409(self):
        self.chat_repository.existing_direct_chat_id = "chat_direct"

        with self.assertRaises(HTTPException) as raised:
            await self.service.create_chat(
                "usr_current",
                CreateDirectChat(type="direct", participantIds=["usr_friend"]),
            )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_current_user_cannot_be_supplied_as_participant(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.create_chat(
                "usr_current",
                CreateGroupChat(type="group", participantIds=["usr_current"]),
            )

        self.assertEqual(raised.exception.status_code, 422)

    async def test_chat_and_message_reads_require_membership(self):
        with self.assertRaises(HTTPException) as chat_error:
            await self.service.get_chat("usr_other", "chat_direct")
        with self.assertRaises(HTTPException) as message_error:
            await self.service.list_messages(
                "usr_other",
                "chat_direct",
                page=1,
                limit=10,
            )

        self.assertEqual(chat_error.exception.status_code, 403)
        self.assertEqual(message_error.exception.status_code, 403)

    async def test_message_listing_is_paginated_and_allows_deleted_sender(self):
        self.chat_repository.messages = [
            ChatMessage(
                id="msg_1",
                chatId="chat_direct",
                senderId=None,
                message="Historical message",
                createdAt=datetime.now(timezone.utc),
            )
        ]

        response = await self.service.list_messages(
            "usr_current",
            "chat_direct",
            page=1,
            limit=10,
        )

        self.assertIsNone(response.messages[0].senderId)
        self.assertEqual(response.pagination.totalItems, 1)
        self.assertEqual(
            self.chat_repository.last_message_page,
            ("chat_direct", 0, 10),
        )

    async def test_first_one_sided_message_does_not_increase_closeness(self):
        message = await self.service.send_message(
            "usr_current",
            "chat_direct",
            SendMessage(message="Hello"),
        )

        self.assertEqual(message.message, "Hello")
        self.assertEqual(self.friend_repository.increases, [])
        self.assertIsNone(self.chat_repository.marked_activity)

    async def test_first_mutual_activity_of_day_increases_closeness(self):
        self.chat_repository.other_messaged_today = True

        await self.service.send_message(
            "usr_current",
            "chat_direct",
            SendMessage(message="Reply"),
        )

        self.assertEqual(len(self.friend_repository.increases), 1)
        self.assertEqual(
            self.friend_repository.increases[0][0:2],
            ("usr_current", "usr_friend"),
        )
        self.assertEqual(
            self.chat_repository.marked_activity,
            ("chat_direct", datetime.now(timezone.utc).date()),
        )

    async def test_closeness_only_increases_once_per_day(self):
        self.chat_repository.other_messaged_today = True
        self.chat_repository.last_activity_dates["chat_direct"] = datetime.now(
            timezone.utc
        ).date()

        await self.service.send_message(
            "usr_current",
            "chat_direct",
            SendMessage(message="Another reply"),
        )

        self.assertEqual(self.friend_repository.increases, [])

    async def test_group_messages_do_not_increase_closeness(self):
        self.chat_repository.other_messaged_today = True

        await self.service.send_message(
            "usr_current",
            "chat_group",
            SendMessage(message="Hello group"),
        )

        self.assertEqual(self.friend_repository.increases, [])

    async def test_missing_friendship_keeps_message_without_score(self):
        self.chat_repository.other_messaged_today = True
        self.friend_repository.increase_result = False

        message = await self.service.send_message(
            "usr_current",
            "chat_direct",
            SendMessage(message="Still chatting"),
        )

        self.assertEqual(message.message, "Still chatting")
        self.assertIsNotNone(self.chat_repository.marked_activity)

    async def test_neo4j_failure_rolls_back_qualifying_message(self):
        self.chat_repository.other_messaged_today = True
        self.friend_repository.increase_error = RuntimeError("Neo4j unavailable")

        with self.assertRaises(RuntimeError):
            await self.service.send_message(
                "usr_current",
                "chat_direct",
                SendMessage(message="Reply"),
            )

        self.assertTrue(self.connection.transactions[-1].rolled_back)

    async def test_standalone_group_participant_can_add_member(self):
        membership = await self.service.add_member(
            "usr_current",
            "chat_group",
            ChatMemberCreate(userId="usr_other"),
        )

        self.assertEqual(membership.userId, "usr_other")
        self.assertIn("usr_other", self.chat_repository.chats["chat_group"].participantIds)

    async def test_direct_and_group_linked_membership_changes_return_409(self):
        with self.assertRaises(HTTPException) as direct_error:
            await self.service.add_member(
                "usr_current",
                "chat_direct",
                ChatMemberCreate(userId="usr_other"),
            )

        self.group_repository.linked_chat_ids.add("chat_group")
        with self.assertRaises(HTTPException) as group_error:
            await self.service.add_member(
                "usr_current",
                "chat_group",
                ChatMemberCreate(userId="usr_other"),
            )

        self.assertEqual(direct_error.exception.status_code, 409)
        self.assertEqual(group_error.exception.status_code, 409)

    async def test_final_standalone_member_leaving_deletes_chat(self):
        self.chat_repository.chats["chat_group"].participantIds = ["usr_current"]

        await self.service.leave_chat("usr_current", "chat_group")

        self.assertEqual(self.chat_repository.deleted_chat, "chat_group")
        self.assertNotIn("chat_group", self.chat_repository.chats)

    async def test_direct_and_group_linked_chats_cannot_be_left(self):
        with self.assertRaises(HTTPException) as direct_error:
            await self.service.leave_chat("usr_current", "chat_direct")

        self.group_repository.linked_chat_ids.add("chat_group")
        with self.assertRaises(HTTPException) as group_error:
            await self.service.leave_chat("usr_current", "chat_group")

        self.assertEqual(direct_error.exception.status_code, 409)
        self.assertEqual(group_error.exception.status_code, 409)


class RecordingPsqlConnection:
    def __init__(self):
        self.calls = []

    async def fetchval(self, query, *parameters):
        self.calls.append(("fetchval", query, parameters))
        return None

    async def fetch(self, query, *parameters):
        self.calls.append(("fetch", query, parameters))
        return []


class ChatRepositoryQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_pair_lock_and_message_ordering_are_deterministic(self):
        connection = RecordingPsqlConnection()

        await ChatPsqlRepository.acquire_direct_pair_lock(connection, "a:b")
        await ChatPsqlRepository.list_messages(
            connection,
            "chat_1",
            skip=0,
            limit=10,
        )

        self.assertIn("pg_advisory_xact_lock", connection.calls[0][1])
        self.assertIn(
            "ORDER BY created_at DESC, id DESC",
            connection.calls[1][1],
        )

    async def test_chat_list_orders_by_latest_message_activity(self):
        connection = RecordingPsqlConnection()

        await ChatPsqlRepository.list_user_chats(
            connection,
            "usr_current",
            skip=0,
            limit=10,
        )

        query = connection.calls[0][1]
        self.assertIn("SELECT max(message.created_at)", query)
        self.assertIn("DESC NULLS LAST", query)
        self.assertIn("chat.created_at DESC", query)


class FakeNeoResult:
    def __init__(self, record):
        self.record = record

    async def single(self):
        return self.record


class RecordingNeoTransaction:
    def __init__(self, record):
        self.record = record
        self.calls = []

    async def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeNeoResult(self.record)


class ClosenessRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_increase_applies_half_life_decay_and_daily_increment(self):
        transaction = RecordingNeoTransaction({"closeness": 0.6})
        interaction_at = datetime.now(timezone.utc)

        updated = await FriendNeoRepository.increase_closeness(
            transaction,
            "usr_one",
            "usr_two",
            interaction_at,
        )

        query, parameters = transaction.calls[0]
        self.assertTrue(updated)
        self.assertIn("/ 2592000.0", query)
        self.assertIn("decayedCloseness + 0.10", query)
        self.assertIn("friendship.closenessUpdatedAt = interactionAt", query)
        self.assertEqual(parameters["interaction_at"], interaction_at)

    async def test_effective_closeness_decays_on_read(self):
        transaction = RecordingNeoTransaction({"closeness": 0.25})
        as_of = datetime.now(timezone.utc)

        closeness = await FriendNeoRepository.effective_closeness(
            transaction,
            "usr_one",
            "usr_two",
            as_of,
        )

        query, _ = transaction.calls[0]
        self.assertEqual(closeness, 0.25)
        self.assertIn("2.0 ^", query)
        self.assertIn("asOf.epochSeconds", query)


if __name__ == "__main__":
    unittest.main()
