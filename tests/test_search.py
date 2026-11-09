import unittest

from fastapi import HTTPException

from app.models.groups import ArtistGroupTag, GroupRecord
from app.models.search import SearchUser
from app.repositories.group_neo_repository import GroupNeoRepository
from app.repositories.user_psql_repository import UserPsqlRepository
from app.services.search_services import SearchService


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self):
        self.connection = object()

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


class FakeDriver:
    def session(self):
        return FakeSession()


class FakeUserRepository:
    def __init__(self):
        self.total = 12
        self.users = [SearchUser(id="usr_alice", username="Alice")]
        self.count_call = None
        self.search_call = None

    async def count_search_users(
        self,
        connection,
        current_user_id,
        query,
    ):
        self.count_call = (connection, current_user_id, query)
        return self.total

    async def search_users(
        self,
        connection,
        current_user_id,
        query,
        skip,
        limit,
    ):
        self.search_call = (
            connection,
            current_user_id,
            query,
            skip,
            limit,
        )
        return self.users


class FakeGroupRepository:
    def __init__(self):
        self.total = 3
        self.records = [
            GroupRecord(
                id="grp_indie",
                psql_chat_id="chat_indie",
                owner_id="usr_owner",
                name="Indie Fans",
                description="Discuss independent music",
            )
        ]
        self.tags = [
            ArtistGroupTag(
                type="artist",
                artistId="artist_1",
                name="Artist One",
            )
        ]
        self.count_call = None
        self.search_call = None
        self.tag_calls = []

    async def count_search_groups(self, transaction, query):
        self.count_call = (transaction, query)
        return self.total

    async def search_group_records(
        self,
        transaction,
        query,
        skip,
        limit,
    ):
        self.search_call = (transaction, query, skip, limit)
        return self.records

    async def list_tags(self, transaction, group_id):
        self.tag_calls.append((transaction, group_id))
        return self.tags


class SearchServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pool = FakePool()
        self.user_repository = FakeUserRepository()
        self.group_repository = FakeGroupRepository()
        self.service = SearchService(
            pg_pool=self.pool,
            neo4j_driver=FakeDriver(),
            user_psql_repository=self.user_repository,
            group_neo_repository=self.group_repository,
        )

    async def test_user_search_normalizes_query_and_excludes_current_user(self):
        response = await self.service.search_users(
            current_user_id="usr_current",
            query="  ALIce  ",
            page=2,
            limit=5,
        )

        self.assertEqual(
            self.user_repository.count_call,
            (self.pool.connection, "usr_current", "alice"),
        )
        self.assertEqual(
            self.user_repository.search_call,
            (self.pool.connection, "usr_current", "alice", 5, 5),
        )
        self.assertEqual(response.users[0].username, "Alice")
        self.assertEqual(response.pagination.totalItems, 12)
        self.assertEqual(response.pagination.totalPages, 3)

    async def test_group_search_returns_full_groups_with_tags(self):
        response = await self.service.search_groups(
            query="  INDIE ",
            page=1,
            limit=10,
        )

        self.assertEqual(self.group_repository.count_call[1], "indie")
        self.assertEqual(self.group_repository.search_call[1:], ("indie", 0, 10))
        self.assertEqual(response.groups[0].ownerId, "usr_owner")
        self.assertEqual(response.groups[0].tags[0].artistId, "artist_1")
        self.assertEqual(response.pagination.totalItems, 3)

    async def test_empty_results_have_zero_pages(self):
        self.user_repository.total = 0
        self.user_repository.users = []

        response = await self.service.search_users(
            current_user_id="usr_current",
            query="nobody",
            page=1,
            limit=10,
        )

        self.assertEqual(response.users, [])
        self.assertEqual(response.pagination.totalPages, 0)

    async def test_blank_query_returns_422(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.search_users(
                current_user_id="usr_current",
                query="   ",
                page=1,
                limit=10,
            )

        self.assertEqual(raised.exception.status_code, 422)


class FakePsqlConnection:
    def __init__(self):
        self.calls = []

    async def fetchval(self, query, *parameters):
        self.calls.append(("fetchval", query, parameters))
        return 1

    async def fetch(self, query, *parameters):
        self.calls.append(("fetch", query, parameters))
        return [{"id": "usr_percent", "username": "%_Listener"}]


class UserSearchRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_treats_wildcards_literally_and_ranks_matches(self):
        connection = FakePsqlConnection()
        repository = UserPsqlRepository()

        total = await repository.count_search_users(
            connection,
            "usr_current",
            "%_",
        )
        users = await repository.search_users(
            connection,
            "usr_current",
            "%_",
            skip=0,
            limit=10,
        )

        self.assertEqual(total, 1)
        self.assertEqual(users[0].id, "usr_percent")
        for _, query, parameters in connection.calls:
            self.assertIn("strpos(lower(username), $2)", query)
            self.assertEqual(parameters[0:2], ("usr_current", "%_"))
        search_query = connection.calls[1][1]
        self.assertIn("lower(username) = $2", search_query)
        self.assertIn("strpos(lower(username), $2) = 1", search_query)
        self.assertIn("id <> $1", search_query)


class FakeNeoResult:
    def __init__(self, records):
        self.records = records
        self.index = 0

    async def single(self):
        return self.records[0] if self.records else None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.records):
            raise StopAsyncIteration
        record = self.records[self.index]
        self.index += 1
        return record


class FakeNeoTransaction:
    def __init__(self):
        self.calls = []

    async def run(self, query_text, **parameters):
        self.calls.append((query_text, parameters))
        if "count(group) AS total" in query_text:
            return FakeNeoResult([{"total": 1}])
        return FakeNeoResult(
            [
                {
                    "id": "grp_indie",
                    "psqlChatId": "chat_indie",
                    "ownerId": "usr_owner",
                    "name": "Indie Fans",
                    "description": "Discuss independent music",
                }
            ]
        )


class GroupSearchRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_covers_public_text_and_deduplicates_groups(self):
        transaction = FakeNeoTransaction()

        total = await GroupNeoRepository.count_search_groups(transaction, "indie")
        records = await GroupNeoRepository.search_group_records(
            transaction,
            "indie",
            skip=0,
            limit=10,
        )

        self.assertEqual(total, 1)
        self.assertEqual(records[0].id, "grp_indie")
        count_query, count_parameters = transaction.calls[0]
        search_query, search_parameters = transaction.calls[1]
        self.assertIn("group.name", count_query)
        self.assertIn("group.description", count_query)
        self.assertIn("tag.name", count_query)
        self.assertIn("collect(DISTINCT", count_query)
        self.assertIn("STARTS WITH", search_query)
        self.assertIn("ORDER BY relevance", search_query)
        self.assertEqual(count_parameters, {"search_query": "indie"})
        self.assertEqual(
            search_parameters,
            {"search_query": "indie", "skip": 0, "limit": 10},
        )


if __name__ == "__main__":
    unittest.main()
