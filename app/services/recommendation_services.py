from datetime import datetime, timezone
from math import ceil

from neo4j import AsyncDriver

from app.models.common import Pagination
from app.models.recommendations import (
    PaginatedArtistGroupRecommendations,
    PaginatedArtistUserRecommendations,
    PaginatedFriendGroupRecommendations,
    PaginatedFriendUserRecommendations,
    PaginatedGenreGroupRecommendations,
    PaginatedSongUserRecommendations,
    RecommendationPeriod,
)
from app.repositories.recommendation_neo_repository import (
    RecommendationNeoRepository,
)


class RecommendationService:
    def __init__(
        self,
        neo4j_driver: AsyncDriver,
        recommendation_neo_repository: RecommendationNeoRepository,
    ):
        self.neo4j_driver = neo4j_driver
        self.recommendation_neo_repository = recommendation_neo_repository

    @staticmethod
    def _pagination(page: int, limit: int, total: int) -> Pagination:
        return Pagination(
            page=page,
            limit=limit,
            totalItems=total,
            totalPages=ceil(total / limit) if total else 0,
        )

    async def recommend_friends_by_artists(
        self,
        user_id: str,
        period: RecommendationPeriod,
        page: int,
        limit: int,
    ) -> PaginatedArtistUserRecommendations:
        async def read(transaction):
            total = await (
                self.recommendation_neo_repository.count_friend_recommendations_by_artists(
                    transaction,
                    user_id,
                    period.score_property,
                )
            )
            items = await self.recommendation_neo_repository.list_friend_recommendations_by_artists(
                transaction,
                user_id,
                period.score_property,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedArtistUserRecommendations(
                items=items,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def recommend_friends_by_songs(
        self,
        user_id: str,
        period: RecommendationPeriod,
        page: int,
        limit: int,
    ) -> PaginatedSongUserRecommendations:
        async def read(transaction):
            total = await self.recommendation_neo_repository.count_friend_recommendations_by_songs(
                transaction,
                user_id,
                period.score_property,
            )
            items = await self.recommendation_neo_repository.list_friend_recommendations_by_songs(
                transaction,
                user_id,
                period.score_property,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedSongUserRecommendations(
                items=items,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def recommend_friends_by_friends(
        self,
        user_id: str,
        page: int,
        limit: int,
    ) -> PaginatedFriendUserRecommendations:
        as_of = datetime.now(timezone.utc)

        async def read(transaction):
            total = await (
                self.recommendation_neo_repository.count_friend_recommendations_by_friends(
                    transaction,
                    user_id,
                )
            )
            items = await self.recommendation_neo_repository.list_friend_recommendations_by_friends(
                transaction,
                user_id,
                as_of,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedFriendUserRecommendations(
                items=items,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def recommend_groups_by_artists(
        self,
        user_id: str,
        period: RecommendationPeriod,
        page: int,
        limit: int,
    ) -> PaginatedArtistGroupRecommendations:
        async def read(transaction):
            total = await self.recommendation_neo_repository.count_group_recommendations_by_artists(
                transaction,
                user_id,
                period.score_property,
            )
            items = await self.recommendation_neo_repository.list_group_recommendations_by_artists(
                transaction,
                user_id,
                period.score_property,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedArtistGroupRecommendations(
                items=items,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def recommend_groups_by_genres(
        self,
        user_id: str,
        period: RecommendationPeriod,
        page: int,
        limit: int,
    ) -> PaginatedGenreGroupRecommendations:
        async def read(transaction):
            total = await self.recommendation_neo_repository.count_group_recommendations_by_genres(
                transaction,
                user_id,
                period.score_property,
            )
            items = await self.recommendation_neo_repository.list_group_recommendations_by_genres(
                transaction,
                user_id,
                period.score_property,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedGenreGroupRecommendations(
                items=items,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def recommend_groups_by_friends(
        self,
        user_id: str,
        page: int,
        limit: int,
    ) -> PaginatedFriendGroupRecommendations:
        as_of = datetime.now(timezone.utc)

        async def read(transaction):
            total = await self.recommendation_neo_repository.count_group_recommendations_by_friends(
                transaction,
                user_id,
            )
            items = await self.recommendation_neo_repository.list_group_recommendations_by_friends(
                transaction,
                user_id,
                as_of,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedFriendGroupRecommendations(
                items=items,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)
