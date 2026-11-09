from datetime import datetime

from app.models.friends import (
    FriendRequest,
    FriendRequestDirection,
    FriendRequestStatusEnum,
    FriendSummary,
    FriendshipStatusEnum,
)


class FriendNeoRepository:
    @staticmethod
    async def user_exists(transaction, user_id: str) -> bool:
        result = await transaction.run(
            "MATCH (u:User {psqlId: $user_id}) RETURN count(u) = 1 AS exists",
            user_id=user_id,
        )
        record = await result.single()
        return bool(record and record["exists"])

    @staticmethod
    async def count_friends(transaction, user_id: str) -> int:
        result = await transaction.run(
            """
            MATCH (user:User {psqlId: $user_id})
            OPTIONAL MATCH (user)-[:FRIENDS_WITH]-(friend:User)
            RETURN count(DISTINCT friend) AS total
            """,
            user_id=user_id,
        )
        record = await result.single()
        return int(record["total"]) if record else 0

    @staticmethod
    async def list_friends(
        transaction,
        user_id: str,
        skip: int,
        limit: int,
    ) -> list[FriendSummary]:
        result = await transaction.run(
            """
            MATCH (user:User {psqlId: $user_id})-[:FRIENDS_WITH]-(friend:User)
            RETURN friend.psqlId AS id, friend.username AS username
            ORDER BY toLower(friend.username), friend.psqlId
            SKIP $skip
            LIMIT $limit
            """,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )
        return [
            FriendSummary(id=record["id"], username=record["username"])
            async for record in result
        ]

    @staticmethod
    async def friendship_exists(transaction, first_user_id: str, second_user_id: str) -> bool:
        result = await transaction.run(
            """
            MATCH (first:User {psqlId: $first_user_id})
            MATCH (second:User {psqlId: $second_user_id})
            OPTIONAL MATCH (first)-[friendship:FRIENDS_WITH]-(second)
            RETURN friendship IS NOT NULL AS exists
            """,
            first_user_id=first_user_id,
            second_user_id=second_user_id,
        )
        record = await result.single()
        return bool(record and record["exists"])

    @staticmethod
    async def get_friendship_status(
        transaction,
        current_user_id: str,
        target_user_id: str,
    ) -> FriendshipStatusEnum:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $current_user_id})
            MATCH (target:User {psqlId: $target_user_id})
            OPTIONAL MATCH (current)-[friendship:FRIENDS_WITH]-(target)
            OPTIONAL MATCH (current)-[outgoing:REQUESTED_FRIENDSHIP]->(target)
            OPTIONAL MATCH (current)<-[incoming:REQUESTED_FRIENDSHIP]-(target)
            RETURN CASE
                WHEN friendship IS NOT NULL THEN 'friends'
                WHEN incoming IS NOT NULL THEN 'pending_incoming'
                WHEN outgoing IS NOT NULL THEN 'pending_outgoing'
                ELSE 'none'
            END AS status
            """,
            current_user_id=current_user_id,
            target_user_id=target_user_id,
        )
        record = await result.single()
        return FriendshipStatusEnum(record["status"])

    @staticmethod
    async def delete_friendship(
        transaction,
        current_user_id: str,
        target_user_id: str,
    ) -> bool:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $current_user_id})
                  -[friendship:FRIENDS_WITH]-
                  (target:User {psqlId: $target_user_id})
            WITH collect(friendship) AS friendships
            FOREACH (relationship IN friendships | DELETE relationship)
            RETURN size(friendships) AS deleted
            """,
            current_user_id=current_user_id,
            target_user_id=target_user_id,
        )
        record = await result.single()
        return bool(record and record["deleted"] > 0)

    @staticmethod
    async def pending_request_exists(
        transaction,
        first_user_id: str,
        second_user_id: str,
    ) -> bool:
        result = await transaction.run(
            """
            MATCH (first:User {psqlId: $first_user_id})
                  -[request:REQUESTED_FRIENDSHIP]-
                  (second:User {psqlId: $second_user_id})
            RETURN count(request) > 0 AS exists
            """,
            first_user_id=first_user_id,
            second_user_id=second_user_id,
        )
        record = await result.single()
        return bool(record and record["exists"])

    @staticmethod
    async def create_request(
        transaction,
        request_id: str,
        pair_key: str,
        sender_id: str,
        target_user_id: str,
        created_at: datetime,
    ) -> FriendRequest:
        result = await transaction.run(
            """
            MATCH (sender:User {psqlId: $sender_id})
            MATCH (target:User {psqlId: $target_user_id})
            CREATE (sender)-[request:REQUESTED_FRIENDSHIP {
                requestId: $request_id,
                pairKey: $pair_key,
                status: 'pending',
                createdAt: $created_at
            }]->(target)
            RETURN request.requestId AS requestId,
                   sender.psqlId AS senderId,
                   target.psqlId AS targetUserId,
                   request.status AS status,
                   request.createdAt AS createdAt
            """,
            request_id=request_id,
            pair_key=pair_key,
            sender_id=sender_id,
            target_user_id=target_user_id,
            created_at=created_at,
        )
        record = await result.single(strict=True)
        return FriendNeoRepository._request_from_record(record)

    @staticmethod
    async def count_requests(
        transaction,
        user_id: str,
        direction: FriendRequestDirection,
    ) -> int:
        result = await transaction.run(
            """
            MATCH (user:User {psqlId: $user_id})-[request:REQUESTED_FRIENDSHIP]-(other:User)
            WHERE $direction = 'all'
               OR ($direction = 'incoming' AND endNode(request) = user)
               OR ($direction = 'outgoing' AND startNode(request) = user)
            RETURN count(request) AS total
            """,
            user_id=user_id,
            direction=direction.value,
        )
        record = await result.single()
        return int(record["total"]) if record else 0

    @staticmethod
    async def list_requests(
        transaction,
        user_id: str,
        direction: FriendRequestDirection,
        skip: int,
        limit: int,
    ) -> list[FriendRequest]:
        result = await transaction.run(
            """
            MATCH (user:User {psqlId: $user_id})-[request:REQUESTED_FRIENDSHIP]-(other:User)
            WHERE $direction = 'all'
               OR ($direction = 'incoming' AND endNode(request) = user)
               OR ($direction = 'outgoing' AND startNode(request) = user)
            WITH request, startNode(request) AS sender, endNode(request) AS target
            RETURN request.requestId AS requestId,
                   sender.psqlId AS senderId,
                   target.psqlId AS targetUserId,
                   request.status AS status,
                   request.createdAt AS createdAt
            ORDER BY request.createdAt DESC, request.requestId
            SKIP $skip
            LIMIT $limit
            """,
            user_id=user_id,
            direction=direction.value,
            skip=skip,
            limit=limit,
        )
        return [FriendNeoRepository._request_from_record(record) async for record in result]

    @staticmethod
    async def select_request(transaction, request_id: str) -> FriendRequest | None:
        result = await transaction.run(
            """
            MATCH (sender:User)-[request:REQUESTED_FRIENDSHIP {requestId: $request_id}]->(target:User)
            RETURN request.requestId AS requestId,
                   sender.psqlId AS senderId,
                   target.psqlId AS targetUserId,
                   request.status AS status,
                   request.createdAt AS createdAt
            """,
            request_id=request_id,
        )
        record = await result.single()
        return FriendNeoRepository._request_from_record(record)

    @staticmethod
    async def create_friendship(
        transaction,
        first_user_id: str,
        second_user_id: str,
    ) -> None:
        result = await transaction.run(
            """
            MATCH (first:User {psqlId: $first_user_id})
            MATCH (second:User {psqlId: $second_user_id})
            WITH CASE WHEN first.psqlId < second.psqlId THEN first ELSE second END AS left,
                 CASE WHEN first.psqlId < second.psqlId THEN second ELSE first END AS right
            CREATE (left)-[:FRIENDS_WITH {
                closeness: 0.0,
                closenessUpdatedAt: datetime()
            }]->(right)
            """,
            first_user_id=first_user_id,
            second_user_id=second_user_id,
        )
        await result.consume()

    @staticmethod
    async def increase_closeness(
        transaction,
        first_user_id: str,
        second_user_id: str,
        interaction_at: datetime,
    ) -> bool:
        result = await transaction.run(
            """
            MATCH (:User {psqlId: $first_user_id})
                  -[friendship:FRIENDS_WITH]-
                  (:User {psqlId: $second_user_id})
            WITH friendship, $interaction_at AS interactionAt
            WITH friendship,
                 interactionAt,
                 CASE
                     WHEN friendship.closenessUpdatedAt IS NULL THEN 0.0
                     ELSE toFloat(
                         interactionAt.epochSeconds
                         - friendship.closenessUpdatedAt.epochSeconds
                     ) / 2592000.0
                 END AS elapsedHalfLives
            WITH friendship,
                 interactionAt,
                 coalesce(friendship.closeness, 0.0)
                 * (2.0 ^ (0.0 - CASE
                     WHEN elapsedHalfLives < 0.0 THEN 0.0
                     ELSE elapsedHalfLives
                 END)) AS decayedCloseness
            SET friendship.closeness = CASE
                    WHEN decayedCloseness + 0.10 > 1.0 THEN 1.0
                    ELSE decayedCloseness + 0.10
                END,
                friendship.closenessUpdatedAt = interactionAt
            RETURN friendship.closeness AS closeness
            """,
            first_user_id=first_user_id,
            second_user_id=second_user_id,
            interaction_at=interaction_at,
        )
        return await result.single() is not None

    @staticmethod
    async def effective_closeness(
        transaction,
        first_user_id: str,
        second_user_id: str,
        as_of: datetime,
    ) -> float | None:
        result = await transaction.run(
            """
            MATCH (:User {psqlId: $first_user_id})
                  -[friendship:FRIENDS_WITH]-
                  (:User {psqlId: $second_user_id})
            WITH friendship, $as_of AS asOf
            WITH friendship,
                 CASE
                     WHEN friendship.closenessUpdatedAt IS NULL THEN 0.0
                     ELSE toFloat(
                         asOf.epochSeconds
                         - friendship.closenessUpdatedAt.epochSeconds
                     ) / 2592000.0
                 END AS elapsedHalfLives
            RETURN coalesce(friendship.closeness, 0.0)
                   * (2.0 ^ (0.0 - CASE
                       WHEN elapsedHalfLives < 0.0 THEN 0.0
                       ELSE elapsedHalfLives
                   END)) AS closeness
            """,
            first_user_id=first_user_id,
            second_user_id=second_user_id,
            as_of=as_of,
        )
        record = await result.single()
        return float(record["closeness"]) if record else None

    @staticmethod
    async def delete_request(transaction, request_id: str) -> bool:
        result = await transaction.run(
            """
            MATCH ()-[request:REQUESTED_FRIENDSHIP {requestId: $request_id}]->()
            WITH collect(request) AS requests
            FOREACH (relationship IN requests | DELETE relationship)
            RETURN size(requests) AS deleted
            """,
            request_id=request_id,
        )
        record = await result.single()
        return bool(record and record["deleted"] > 0)

    @staticmethod
    def _request_from_record(record) -> FriendRequest | None:
        if record is None:
            return None
        created_at = record["createdAt"]
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        return FriendRequest(
            requestId=record["requestId"],
            senderId=record["senderId"],
            targetUserId=record["targetUserId"],
            status=FriendRequestStatusEnum(record["status"]),
            createdAt=created_at,
        )
