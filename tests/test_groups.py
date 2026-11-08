import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from neo4j.time import DateTime
from pydantic import ValidationError

from app.models.groups import (
    ArtistGroupTag,
    ArtistGroupTagInput,
    GenreGroupTag,
    GenreGroupTagInput,
    GroupCreate,
    GroupMember,
    GroupMemberCreate,
    GroupMemberRole,
    GroupRecord,
    GroupTagsReplace,
    GroupUpdate,
)
from app.repositories.group_neo_repository import GroupNeoRepository
from app.services.group_services import GroupService


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


class FakeChatRepository:
    def __init__(self):
        self.created = None
        self.deleted = None
        self.added = None
        self.removed = None
        self.delete_result = True
        self.remove_result = True

    async def create_group_chat(self, connection, chat_id, owner_id):
        self.created = (chat_id, owner_id)

    async def delete_chat(self, connection, chat_id):
        self.deleted = chat_id
        return self.delete_result

    async def add_participant(self, connection, chat_id, user_id):
        self.added = (chat_id, user_id)

    async def remove_participant(self, connection, chat_id, user_id):
        self.removed = (chat_id, user_id)
        return self.remove_result


class FakeGroupRepository:
    def __init__(self):
        self.users = {
            "usr_owner": "Owner",
            "usr_member": "Member",
            "usr_other": "Other",
        }
        self.groups = {
            "grp_existing": GroupRecord(
                id="grp_existing",
                psql_chat_id="chat_existing",
                owner_id="usr_owner",
                name="Existing Group",
                description="An existing group",
            )
        }
        self.tags = {
            "grp_existing": [
                ArtistGroupTag(
                    type="artist",
                    artistId="artist_1",
                    name="Artist One",
                )
            ]
        }
        joined_at = datetime.now(timezone.utc)
        self.members = {
            "grp_existing": {
                "usr_owner": GroupMember(
                    id="usr_owner",
                    username="Owner",
                    role=GroupMemberRole.owner,
                    joinedAt=joined_at,
                ),
                "usr_member": GroupMember(
                    id="usr_member",
                    username="Member",
                    role=GroupMemberRole.member,
                    joinedAt=joined_at,
                ),
            }
        }
        self.artists = {
            "artist_1": ArtistGroupTag(
                type="artist",
                artistId="artist_1",
                name="Artist One",
            )
        }
        self.genres = {
            "genre_1": GenreGroupTag(
                type="genre",
                genreId="genre_1",
                name="Indie",
            )
        }
        self.error_on_create_group = None
        self.error_on_delete_group = None
        self.error_on_create_membership = None
        self.error_on_delete_membership = None
        self.last_group_page = None
        self.last_member_page = None

    async def user_exists(self, transaction, user_id):
        return user_id in self.users

    async def count_groups(self, transaction):
        return len(self.groups)

    async def list_group_records(self, transaction, skip, limit):
        self.last_group_page = (skip, limit)
        return list(self.groups.values())[skip : skip + limit]

    async def select_group(self, transaction, group_id):
        return self.groups.get(group_id)

    async def create_group(
        self,
        transaction,
        group_id,
        chat_id,
        owner_id,
        name,
        description,
        joined_at,
    ):
        if self.error_on_create_group is not None:
            raise self.error_on_create_group
        record = GroupRecord(
            id=group_id,
            psql_chat_id=chat_id,
            owner_id=owner_id,
            name=name,
            description=description,
        )
        self.groups[group_id] = record
        self.members[group_id] = {
            owner_id: GroupMember(
                id=owner_id,
                username=self.users[owner_id],
                role=GroupMemberRole.owner,
                joinedAt=joined_at,
            )
        }
        return record

    async def update_group(self, transaction, group_id, updates):
        current = self.groups[group_id]
        updated = current.model_copy(update=updates)
        self.groups[group_id] = updated
        return updated

    async def delete_group(self, transaction, group_id):
        if self.error_on_delete_group is not None:
            raise self.error_on_delete_group
        return self.groups.pop(group_id, None) is not None

    async def membership_exists(self, transaction, group_id, user_id):
        return user_id in self.members.get(group_id, {})

    async def create_membership(self, transaction, group_id, user_id, joined_at):
        if self.error_on_create_membership is not None:
            raise self.error_on_create_membership
        member = GroupMember(
            id=user_id,
            username=self.users[user_id],
            role=GroupMemberRole.member,
            joinedAt=joined_at,
        )
        self.members[group_id][user_id] = member
        return member

    async def select_member(self, transaction, group_id, user_id):
        return self.members.get(group_id, {}).get(user_id)

    async def count_members(self, transaction, group_id):
        return len(self.members.get(group_id, {}))

    async def list_members(self, transaction, group_id, skip, limit):
        self.last_member_page = (skip, limit)
        members = list(self.members.get(group_id, {}).values())
        return members[skip : skip + limit]

    async def delete_membership(self, transaction, group_id, user_id):
        if self.error_on_delete_membership is not None:
            raise self.error_on_delete_membership
        return self.members.get(group_id, {}).pop(user_id, None) is not None

    async def select_artist_tag(self, transaction, artist_id):
        return self.artists.get(artist_id)

    async def select_genre_tag(self, transaction, genre_id):
        return self.genres.get(genre_id)

    async def list_tags(self, transaction, group_id):
        return self.tags.get(group_id, [])

    async def replace_tags(self, transaction, group_id, tags):
        self.tags[group_id] = list(tags)


class GroupModelTests(unittest.TestCase):
    def test_create_strips_text_and_accepts_catalog_ids(self):
        payload = GroupCreate(
            name="  Indie Fans  ",
            description="  Music group  ",
            tags=[
                {"type": "artist", "artistId": "artist_1"},
                {"type": "genre", "genreId": "genre_1"},
            ],
        )

        self.assertEqual(payload.name, "Indie Fans")
        self.assertEqual(payload.description, "Music group")

    def test_duplicate_tags_are_rejected(self):
        with self.assertRaises(ValidationError):
            GroupTagsReplace(
                tags=[
                    {"type": "genre", "genreId": "genre_1"},
                    {"type": "genre", "genreId": "genre_1"},
                ]
            )

    def test_tag_names_are_rejected_in_requests(self):
        with self.assertRaises(ValidationError):
            GroupTagsReplace(
                tags=[
                    {
                        "type": "artist",
                        "artistId": "artist_1",
                        "name": "Client-supplied name",
                    }
                ]
            )

    def test_more_than_ten_tags_are_rejected(self):
        with self.assertRaises(ValidationError):
            GroupTagsReplace(
                tags=[
                    {"type": "artist", "artistId": f"artist_{index}"}
                    for index in range(11)
                ]
            )

    def test_empty_tag_replacement_is_allowed(self):
        self.assertEqual(GroupTagsReplace(tags=[]).tags, [])

    def test_empty_update_is_rejected(self):
        with self.assertRaises(ValidationError):
            GroupUpdate()


class GroupServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.group_repository = FakeGroupRepository()
        self.chat_repository = FakeChatRepository()
        self.service = GroupService(
            pg_pool=FakePool(self.connection),
            neo4j_driver=FakeDriver(),
            group_neo_repository=self.group_repository,
            chat_psql_repository=self.chat_repository,
        )

    async def test_group_listing_is_paginated_and_includes_owner(self):
        response = await self.service.list_groups(page=1, limit=1)

        self.assertEqual(response.groups[0].ownerId, "usr_owner")
        self.assertEqual(response.pagination.page, 1)
        self.assertEqual(response.pagination.totalItems, 1)
        self.assertEqual(response.pagination.totalPages, 1)
        self.assertEqual(self.group_repository.last_group_page, (0, 1))

    async def test_missing_group_returns_404(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.get_group("grp_missing")

        self.assertEqual(raised.exception.status_code, 404)

    async def test_create_group_creates_distinct_chat_and_owner_membership(self):
        group = await self.service.create_group(
            "usr_owner",
            GroupCreate(
                name="New Group",
                description="Description",
                tags=[{"type": "genre", "genreId": "genre_1"}],
            ),
        )

        chat_id, owner_id = self.chat_repository.created
        self.assertTrue(group.id.startswith("grp_"))
        self.assertTrue(chat_id.startswith("chat_"))
        self.assertNotEqual(group.id, chat_id)
        self.assertEqual(owner_id, "usr_owner")
        self.assertEqual(group.ownerId, "usr_owner")
        self.assertEqual(group.tags[0].genreId, "genre_1")
        self.assertEqual(
            self.group_repository.members[group.id]["usr_owner"].role,
            GroupMemberRole.owner,
        )

    async def test_create_rolls_back_postgres_when_neo4j_fails(self):
        self.group_repository.error_on_create_group = RuntimeError("Neo4j unavailable")

        with self.assertRaises(RuntimeError):
            await self.service.create_group(
                "usr_owner",
                GroupCreate(name="New Group", description="Description"),
            )

        self.assertTrue(self.connection.transactions[-1].rolled_back)

    async def test_only_owner_can_update_group(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.update_group(
                "usr_other",
                "grp_existing",
                GroupUpdate(name="Renamed"),
            )

        self.assertEqual(raised.exception.status_code, 403)

    async def test_delete_removes_linked_chat_and_group(self):
        await self.service.delete_group("usr_owner", "grp_existing")

        self.assertEqual(self.chat_repository.deleted, "chat_existing")
        self.assertNotIn("grp_existing", self.group_repository.groups)

    async def test_delete_rolls_back_postgres_when_neo4j_fails(self):
        self.group_repository.error_on_delete_group = RuntimeError("Neo4j unavailable")

        with self.assertRaises(RuntimeError):
            await self.service.delete_group("usr_owner", "grp_existing")

        self.assertTrue(self.connection.transactions[-1].rolled_back)

    async def test_any_user_can_self_join(self):
        member = await self.service.add_member(
            "usr_other",
            "grp_existing",
            payload=None,
        )

        self.assertEqual(member.id, "usr_other")
        self.assertEqual(member.role, GroupMemberRole.member)
        self.assertEqual(
            self.chat_repository.added,
            ("chat_existing", "usr_other"),
        )

    async def test_non_owner_cannot_add_another_user(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.add_member(
                "usr_member",
                "grp_existing",
                GroupMemberCreate(userId="usr_other"),
            )

        self.assertEqual(raised.exception.status_code, 403)

    async def test_duplicate_membership_returns_409(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.add_member(
                "usr_member",
                "grp_existing",
                payload=None,
            )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_join_rolls_back_postgres_when_neo4j_fails(self):
        self.group_repository.error_on_create_membership = RuntimeError(
            "Neo4j unavailable"
        )

        with self.assertRaises(RuntimeError):
            await self.service.add_member(
                "usr_other",
                "grp_existing",
                payload=None,
            )

        self.assertTrue(self.connection.transactions[-1].rolled_back)

    async def test_owner_cannot_leave(self):
        self.group_repository.members["grp_existing"]["usr_owner"] = (
            self.group_repository.members["grp_existing"]["usr_owner"].model_copy(
                update={"role": GroupMemberRole.member}
            )
        )

        with self.assertRaises(HTTPException) as raised:
            await self.service.leave_group("usr_owner", "grp_existing")

        self.assertEqual(raised.exception.status_code, 409)

    async def test_member_can_leave(self):
        await self.service.leave_group("usr_member", "grp_existing")

        self.assertEqual(
            self.chat_repository.removed,
            ("chat_existing", "usr_member"),
        )
        self.assertNotIn("usr_member", self.group_repository.members["grp_existing"])

    async def test_leave_rolls_back_postgres_when_neo4j_fails(self):
        self.group_repository.error_on_delete_membership = RuntimeError(
            "Neo4j unavailable"
        )

        with self.assertRaises(RuntimeError):
            await self.service.leave_group("usr_member", "grp_existing")

        self.assertTrue(self.connection.transactions[-1].rolled_back)

    async def test_only_owner_can_replace_tags(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.replace_tags(
                "usr_member",
                "grp_existing",
                GroupTagsReplace(tags=[]),
            )

        self.assertEqual(raised.exception.status_code, 403)

    async def test_replacing_tags_resolves_catalog_names(self):
        tags = await self.service.replace_tags(
            "usr_owner",
            "grp_existing",
            GroupTagsReplace(
                tags=[
                    ArtistGroupTagInput(type="artist", artistId="artist_1"),
                    GenreGroupTagInput(type="genre", genreId="genre_1"),
                ]
            ),
        )

        self.assertEqual([tag.name for tag in tags], ["Artist One", "Indie"])

    async def test_unknown_tag_returns_404_without_replacing_tags(self):
        original = self.group_repository.tags["grp_existing"]

        with self.assertRaises(HTTPException) as raised:
            await self.service.replace_tags(
                "usr_owner",
                "grp_existing",
                GroupTagsReplace(
                    tags=[{"type": "artist", "artistId": "artist_missing"}]
                ),
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(self.group_repository.tags["grp_existing"], original)


class GroupRepositoryMappingTests(unittest.TestCase):
    def test_neo4j_datetime_is_converted_to_native_datetime(self):
        member = GroupNeoRepository._member(
            {
                "id": "usr_member",
                "username": "Member",
                "role": "member",
                "joinedAt": DateTime.now(),
            }
        )

        self.assertIsInstance(member.joinedAt, datetime)


if __name__ == "__main__":
    unittest.main()
