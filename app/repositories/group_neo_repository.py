from datetime import datetime

from app.models.groups import (
    ArtistGroupTag,
    GroupMember,
    GroupMemberRole,
    GroupRecord,
    GenreGroupTag,
)


class GroupNeoRepository:
    @staticmethod
    async def user_exists(transaction, user_id: str) -> bool:
        result = await transaction.run(
            "MATCH (u:User {psqlId: $user_id}) RETURN count(u) = 1 AS exists",
            user_id=user_id,
        )
        record = await result.single()
        return bool(record and record["exists"])

    @staticmethod
    async def count_groups(transaction) -> int:
        result = await transaction.run(
            "MATCH (group:Group) WHERE group.id IS NOT NULL RETURN count(group) AS total"
        )
        record = await result.single()
        return int(record["total"]) if record else 0

    @staticmethod
    async def list_group_records(transaction, skip: int, limit: int) -> list[GroupRecord]:
        result = await transaction.run(
            """
            MATCH (group:Group)
            WHERE group.id IS NOT NULL
            RETURN group.id AS id,
                   group.psqlChatId AS psqlChatId,
                   group.ownerId AS ownerId,
                   group.name AS name,
                   group.description AS description
            ORDER BY toLower(group.name), group.id
            SKIP $skip
            LIMIT $limit
            """,
            skip=skip,
            limit=limit,
        )
        return [GroupNeoRepository._group_record(record) async for record in result]

    @staticmethod
    async def select_group(transaction, group_id: str) -> GroupRecord | None:
        result = await transaction.run(
            """
            MATCH (group:Group {id: $group_id})
            RETURN group.id AS id,
                   group.psqlChatId AS psqlChatId,
                   group.ownerId AS ownerId,
                   group.name AS name,
                   group.description AS description
            """,
            group_id=group_id,
        )
        return GroupNeoRepository._group_record(await result.single())

    @staticmethod
    async def create_group(
        transaction,
        group_id: str,
        chat_id: str,
        owner_id: str,
        name: str,
        description: str,
        joined_at: datetime,
    ) -> GroupRecord:
        result = await transaction.run(
            """
            MATCH (owner:User {psqlId: $owner_id})
            CREATE (group:Group {
                id: $group_id,
                psqlChatId: $chat_id,
                ownerId: $owner_id,
                name: $name,
                description: $description
            })
            CREATE (owner)-[:PARTS_OF {role: 'owner', joinedAt: $joined_at}]->(group)
            RETURN group.id AS id,
                   group.psqlChatId AS psqlChatId,
                   group.ownerId AS ownerId,
                   group.name AS name,
                   group.description AS description
            """,
            group_id=group_id,
            chat_id=chat_id,
            owner_id=owner_id,
            name=name,
            description=description,
            joined_at=joined_at,
        )
        return GroupNeoRepository._group_record(await result.single(strict=True))

    @staticmethod
    async def update_group(transaction, group_id: str, updates: dict[str, str]) -> GroupRecord:
        assignments = []
        parameters = {"group_id": group_id}
        allowed = {"name", "description"}
        for field, value in updates.items():
            if field not in allowed:
                raise ValueError(f"Unsupported group field: {field}")
            parameters[field] = value
            assignments.append(f"group.{field} = ${field}")

        result = await transaction.run(
            f"""
            MATCH (group:Group {{id: $group_id}})
            SET {', '.join(assignments)}
            RETURN group.id AS id,
                   group.psqlChatId AS psqlChatId,
                   group.ownerId AS ownerId,
                   group.name AS name,
                   group.description AS description
            """,
            **parameters,
        )
        return GroupNeoRepository._group_record(await result.single(strict=True))

    @staticmethod
    async def delete_group(transaction, group_id: str) -> bool:
        result = await transaction.run(
            """
            MATCH (group:Group {id: $group_id})
            DETACH DELETE group
            RETURN 1 AS deleted
            """,
            group_id=group_id,
        )
        record = await result.single()
        return bool(record and record["deleted"] > 0)

    @staticmethod
    async def is_owner(transaction, group_id: str, user_id: str) -> bool:
        result = await transaction.run(
            """
            MATCH (group:Group {id: $group_id})
            RETURN group.ownerId = $user_id AS isOwner
            """,
            group_id=group_id,
            user_id=user_id,
        )
        record = await result.single()
        return bool(record and record["isOwner"])

    @staticmethod
    async def membership_exists(transaction, group_id: str, user_id: str) -> bool:
        result = await transaction.run(
            """
            MATCH (user:User {psqlId: $user_id})-[membership:PARTS_OF]->
                  (group:Group {id: $group_id})
            RETURN count(membership) > 0 AS exists
            """,
            group_id=group_id,
            user_id=user_id,
        )
        record = await result.single()
        return bool(record and record["exists"])

    @staticmethod
    async def create_membership(
        transaction,
        group_id: str,
        user_id: str,
        joined_at: datetime,
    ) -> GroupMember:
        result = await transaction.run(
            """
            MATCH (user:User {psqlId: $user_id})
            MATCH (group:Group {id: $group_id})
            CREATE (user)-[membership:PARTS_OF {role: 'member', joinedAt: $joined_at}]->(group)
            RETURN user.psqlId AS id,
                   user.username AS username,
                   membership.role AS role,
                   membership.joinedAt AS joinedAt
            """,
            group_id=group_id,
            user_id=user_id,
            joined_at=joined_at,
        )
        return GroupNeoRepository._member(await result.single(strict=True))

    @staticmethod
    async def select_member(transaction, group_id: str, user_id: str) -> GroupMember | None:
        result = await transaction.run(
            """
            MATCH (user:User {psqlId: $user_id})-[membership:PARTS_OF]->
                  (group:Group {id: $group_id})
            RETURN user.psqlId AS id,
                   user.username AS username,
                   membership.role AS role,
                   membership.joinedAt AS joinedAt
            """,
            group_id=group_id,
            user_id=user_id,
        )
        return GroupNeoRepository._member(await result.single())

    @staticmethod
    async def count_members(transaction, group_id: str) -> int:
        result = await transaction.run(
            """
            MATCH (:User)-[membership:PARTS_OF]->(:Group {id: $group_id})
            RETURN count(membership) AS total
            """,
            group_id=group_id,
        )
        record = await result.single()
        return int(record["total"]) if record else 0

    @staticmethod
    async def list_members(
        transaction,
        group_id: str,
        skip: int,
        limit: int,
    ) -> list[GroupMember]:
        result = await transaction.run(
            """
            MATCH (user:User)-[membership:PARTS_OF]->(:Group {id: $group_id})
            RETURN user.psqlId AS id,
                   user.username AS username,
                   membership.role AS role,
                   membership.joinedAt AS joinedAt
            ORDER BY CASE membership.role WHEN 'owner' THEN 0 ELSE 1 END,
                     toLower(user.username), user.psqlId
            SKIP $skip
            LIMIT $limit
            """,
            group_id=group_id,
            skip=skip,
            limit=limit,
        )
        return [GroupNeoRepository._member(record) async for record in result]

    @staticmethod
    async def delete_membership(transaction, group_id: str, user_id: str) -> bool:
        result = await transaction.run(
            """
            MATCH (:User {psqlId: $user_id})-[membership:PARTS_OF]->(:Group {id: $group_id})
            WITH collect(membership) AS memberships
            FOREACH (relationship IN memberships | DELETE relationship)
            RETURN size(memberships) AS deleted
            """,
            group_id=group_id,
            user_id=user_id,
        )
        record = await result.single()
        return bool(record and record["deleted"] > 0)

    @staticmethod
    async def select_artist_tag(transaction, artist_id: str) -> ArtistGroupTag | None:
        result = await transaction.run(
            """
            MATCH (artist:Artists {id: $artist_id})
            RETURN artist.id AS id, artist.name AS name
            """,
            artist_id=artist_id,
        )
        record = await result.single()
        if not record:
            return None
        return ArtistGroupTag(type="artist", artistId=record["id"], name=record["name"])

    @staticmethod
    async def select_genre_tag(transaction, genre_id: str) -> GenreGroupTag | None:
        result = await transaction.run(
            """
            MATCH (genre:Genre {id: $genre_id})
            RETURN genre.id AS id, genre.name AS name
            """,
            genre_id=genre_id,
        )
        record = await result.single()
        if not record:
            return None
        return GenreGroupTag(type="genre", genreId=record["id"], name=record["name"])

    @staticmethod
    async def list_tags(transaction, group_id: str):
        result = await transaction.run(
            """
            MATCH (:Group {id: $group_id})-[:TAGGED_WITH]->(tag)
            RETURN labels(tag) AS labels, tag.id AS id, tag.name AS name
            ORDER BY CASE WHEN 'Artists' IN labels(tag) THEN 0 ELSE 1 END,
                     toLower(tag.name), tag.id
            """,
            group_id=group_id,
        )
        tags = []
        async for record in result:
            if "Artists" in record["labels"]:
                tags.append(
                    ArtistGroupTag(
                        type="artist",
                        artistId=record["id"],
                        name=record["name"],
                    )
                )
            else:
                tags.append(GenreGroupTag(type="genre", genreId=record["id"], name=record["name"]))
        return tags

    @staticmethod
    async def replace_tags(transaction, group_id: str, tags) -> None:
        result = await transaction.run(
            """
            MATCH (group:Group {id: $group_id})-[relationship:TAGGED_WITH]->()
            DELETE relationship
            """,
            group_id=group_id,
        )
        await result.consume()

        for tag in tags:
            if tag.type == "artist":
                query = """
                    MATCH (group:Group {id: $group_id})
                    MATCH (tag:Artists {id: $tag_id})
                    CREATE (group)-[:TAGGED_WITH]->(tag)
                """
                tag_id = tag.artistId
            else:
                query = """
                    MATCH (group:Group {id: $group_id})
                    MATCH (tag:Genre {id: $tag_id})
                    CREATE (group)-[:TAGGED_WITH]->(tag)
                """
                tag_id = tag.genreId
            result = await transaction.run(query, group_id=group_id, tag_id=tag_id)
            await result.consume()

    @staticmethod
    def _group_record(record) -> GroupRecord | None:
        if not record:
            return None
        return GroupRecord(
            id=record["id"],
            psql_chat_id=record["psqlChatId"],
            owner_id=record["ownerId"],
            name=record["name"],
            description=record["description"],
        )

    @staticmethod
    def _member(record) -> GroupMember | None:
        if not record:
            return None
        joined_at = record["joinedAt"]
        if hasattr(joined_at, "to_native"):
            joined_at = joined_at.to_native()
        return GroupMember(
            id=record["id"],
            username=record["username"],
            role=GroupMemberRole(record["role"]),
            joinedAt=joined_at,
        )
