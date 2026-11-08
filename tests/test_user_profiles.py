import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.core.security import create_access_token, create_refresh_token
from app.dependencies import verify_access_token
from app.models.users import UserProfileUpdate, UserRecord
from app.services.user_services import UserService


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
        self.transaction_context = AsyncContext(self)

    def transaction(self):
        return self.transaction_context


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return AsyncContext(self.connection)


class FakeUserPsqlRepository:
    def __init__(self, user):
        self.user = user
        self.updates = None
        self.deleted = False

    async def select_by_id(self, connection, user_id):
        return self.user

    async def update_profile(self, connection, user_id, updates):
        self.updates = updates
        if self.user is None:
            return None
        data = self.user.model_dump()
        if "avatar_url" in updates:
            data["avatar_url"] = updates["avatar_url"]
        if "bio" in updates:
            data["bio"] = updates["bio"]
        self.user = UserRecord(**data)
        return self.user

    async def delete(self, connection, user_id):
        if self.user is None:
            return False
        self.deleted = True
        return True


class FakeNeoTransaction:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeNeoSession:
    def __init__(self, transaction):
        self.transaction = transaction

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def begin_transaction(self):
        return self.transaction


class FakeNeoDriver:
    def __init__(self):
        self.transaction = FakeNeoTransaction()

    def session(self):
        return FakeNeoSession(self.transaction)


class FakeUserNeoRepository:
    def __init__(self, error=None):
        self.error = error
        self.deleted_user_id = None

    async def delete_by_psql_id(self, transaction, user_id):
        if self.error is not None:
            raise self.error
        self.deleted_user_id = user_id
        return False


class UserProfileModelTests(unittest.TestCase):
    def test_empty_update_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfileUpdate()

    def test_explicit_null_is_distinct_from_an_omitted_field(self):
        update = UserProfileUpdate(bio=None)

        self.assertEqual(update.model_fields_set, {"bio"})
        self.assertIsNone(update.bio)

    def test_invalid_avatar_url_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfileUpdate(avatarUrl="not-a-url")

    def test_oversized_bio_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfileUpdate(bio="a" * 501)


class UserServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = UserRecord(
            id="usr_a1b2c3d4e5f6",
            username="alex",
            email="alex@example.com",
            avatar_url="https://example.com/avatar.jpg",
            bio="Music enthusiast",
        )
        self.connection = FakeConnection()
        self.psql_repository = FakeUserPsqlRepository(self.user)
        self.neo4j_driver = FakeNeoDriver()
        self.neo4j_repository = FakeUserNeoRepository()
        self.service = UserService(
            pg_pool=FakePool(self.connection),
            neo4j_driver=self.neo4j_driver,
            user_psql_repository=self.psql_repository,
            user_neo_repository=self.neo4j_repository,
        )

    async def test_private_profile_contains_email(self):
        profile = await self.service.get_private_profile(self.user.id)

        self.assertEqual(profile.email, self.user.email)
        self.assertEqual(profile.username, self.user.username)

    async def test_public_profile_does_not_expose_email(self):
        profile = await self.service.get_public_profile(self.user.id)

        self.assertNotIn("email", profile.model_dump())

    async def test_missing_user_returns_404(self):
        self.psql_repository.user = None

        with self.assertRaises(HTTPException) as raised:
            await self.service.get_private_profile("missing")

        self.assertEqual(raised.exception.status_code, 404)

    async def test_update_clears_only_explicitly_supplied_field(self):
        profile = await self.service.update_profile(
            self.user.id,
            UserProfileUpdate(bio=None),
        )

        self.assertEqual(self.psql_repository.updates, {"bio": None})
        self.assertIsNone(profile.bio)
        self.assertIsNotNone(profile.avatarUrl)

    async def test_delete_succeeds_when_neo4j_node_is_missing(self):
        await self.service.delete_user(self.user.id)

        self.assertTrue(self.psql_repository.deleted)
        self.assertEqual(self.neo4j_repository.deleted_user_id, self.user.id)
        self.assertTrue(self.neo4j_driver.transaction.committed)

    async def test_neo4j_failure_rolls_back_both_transactions(self):
        error = RuntimeError("Neo4j unavailable")
        self.neo4j_repository.error = error

        with self.assertRaises(RuntimeError):
            await self.service.delete_user(self.user.id)

        self.assertTrue(self.neo4j_driver.transaction.rolled_back)
        self.assertTrue(self.connection.transaction_context.rolled_back)


class UserProfileAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def test_access_token_is_accepted(self):
        token = create_access_token({"sub": "usr_a1b2c3d4e5f6"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        user_id = await verify_access_token(credentials)

        self.assertEqual(user_id, "usr_a1b2c3d4e5f6")

    async def test_missing_credentials_return_401(self):
        with self.assertRaises(HTTPException) as raised:
            await verify_access_token(None)

        self.assertEqual(raised.exception.status_code, 401)

    async def test_refresh_token_is_rejected(self):
        token = create_refresh_token({"sub": "usr_a1b2c3d4e5f6"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with self.assertRaises(HTTPException) as raised:
            await verify_access_token(credentials)

        self.assertEqual(raised.exception.status_code, 401)

    async def test_invalid_token_is_rejected(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="not-a-jwt",
        )

        with self.assertRaises(HTTPException) as raised:
            await verify_access_token(credentials)

        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
