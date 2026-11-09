import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.models.common import Pagination
from app.models.groups import ArtistGroupTag, Group
from app.models.music import Artist, Genre, Song
from app.models.recommendations import (
    ArtistGroupRecommendations,
    ArtistUserRecommendations,
    FriendGroupRecommendations,
    FriendUserRecommendations,
    GenreGroupRecommendations,
    RecommendationPeriod,
    SongUserRecommendations,
)
from app.models.search import SearchUser
from app.repositories.recommendation_neo_repository import (
    RecommendationNeoRepository,
)
from app.services.recommendation_services import RecommendationService


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


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


class FakeRecommendationRepository:
    def __init__(self):
        self.calls = []
        self.artist = Artist(id="artist_1", name="Artist One")
        self.song = Song(
            id="song_1",
            title="Song One",
            artists=[self.artist],
        )
        self.genre = Genre(id="genre_1", name="Indie")
        self.user = SearchUser(id="usr_candidate", username="Candidate")
        self.friend = SearchUser(id="usr_friend", username="Friend")
        self.group = Group(
            id="grp_1",
            ownerId="usr_owner",
            name="Indie Group",
            description="A group",
            tags=[],
        )

    async def count_friend_recommendations_by_artists(
        self, transaction, user_id, score_property
    ):
        self.calls.append(("count-friend-artists", user_id, score_property))
        return 11

    async def list_friend_recommendations_by_artists(
        self, transaction, user_id, score_property, skip, limit
    ):
        self.calls.append(
            ("list-friend-artists", user_id, score_property, skip, limit)
        )
        return [ArtistUserRecommendations(artist=self.artist, users=[self.user])]

    async def count_friend_recommendations_by_songs(
        self, transaction, user_id, score_property
    ):
        self.calls.append(("count-friend-songs", user_id, score_property))
        return 1

    async def list_friend_recommendations_by_songs(
        self, transaction, user_id, score_property, skip, limit
    ):
        self.calls.append(("list-friend-songs", user_id, score_property, skip, limit))
        return [SongUserRecommendations(song=self.song, users=[self.user])]

    async def count_friend_recommendations_by_friends(self, transaction, user_id):
        self.calls.append(("count-friend-friends", user_id))
        return 1

    async def list_friend_recommendations_by_friends(
        self, transaction, user_id, as_of, skip, limit
    ):
        self.calls.append(("list-friend-friends", user_id, as_of, skip, limit))
        return [FriendUserRecommendations(friend=self.friend, users=[self.user])]

    async def count_group_recommendations_by_artists(
        self, transaction, user_id, score_property
    ):
        self.calls.append(("count-group-artists", user_id, score_property))
        return 1

    async def list_group_recommendations_by_artists(
        self, transaction, user_id, score_property, skip, limit
    ):
        self.calls.append(("list-group-artists", user_id, score_property, skip, limit))
        return [ArtistGroupRecommendations(artist=self.artist, groups=[self.group])]

    async def count_group_recommendations_by_genres(
        self, transaction, user_id, score_property
    ):
        self.calls.append(("count-group-genres", user_id, score_property))
        return 1

    async def list_group_recommendations_by_genres(
        self, transaction, user_id, score_property, skip, limit
    ):
        self.calls.append(("list-group-genres", user_id, score_property, skip, limit))
        return [GenreGroupRecommendations(genre=self.genre, groups=[self.group])]

    async def count_group_recommendations_by_friends(self, transaction, user_id):
        self.calls.append(("count-group-friends", user_id))
        return 1

    async def list_group_recommendations_by_friends(
        self, transaction, user_id, as_of, skip, limit
    ):
        self.calls.append(("list-group-friends", user_id, as_of, skip, limit))
        return [FriendGroupRecommendations(friend=self.friend, groups=[self.group])]


class RecommendationPeriodTests(unittest.TestCase):
    def test_periods_map_to_whitelisted_relationship_properties(self):
        self.assertEqual(
            RecommendationPeriod.short_term.score_property,
            "shortTermScore",
        )
        self.assertEqual(
            RecommendationPeriod.medium_term.score_property,
            "mediumTermScore",
        )
        self.assertEqual(
            RecommendationPeriod.long_term.score_property,
            "longTermScore",
        )

    def test_pagination_limit_is_capped_at_one_hundred(self):
        with self.assertRaises(ValidationError):
            Pagination(
                page=1,
                limit=101,
                totalItems=0,
                totalPages=0,
            )


class RecommendationServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeRecommendationRepository()
        self.service = RecommendationService(FakeDriver(), self.repository)

    async def test_weighted_friend_recommendations_are_paginated(self):
        response = await self.service.recommend_friends_by_artists(
            "usr_current",
            RecommendationPeriod.medium_term,
            page=2,
            limit=10,
        )

        self.assertEqual(response.items[0].artist.id, "artist_1")
        self.assertEqual(response.pagination.totalItems, 11)
        self.assertEqual(response.pagination.totalPages, 2)
        self.assertIn(
            ("list-friend-artists", "usr_current", "mediumTermScore", 10, 10),
            self.repository.calls,
        )

    async def test_all_six_recommendation_flows_return_grouped_items(self):
        responses = [
            await self.service.recommend_friends_by_songs(
                "usr_current", RecommendationPeriod.short_term, 1, 10
            ),
            await self.service.recommend_friends_by_friends("usr_current", 1, 10),
            await self.service.recommend_groups_by_artists(
                "usr_current", RecommendationPeriod.long_term, 1, 10
            ),
            await self.service.recommend_groups_by_genres(
                "usr_current", RecommendationPeriod.medium_term, 1, 10
            ),
            await self.service.recommend_groups_by_friends("usr_current", 1, 10),
        ]

        self.assertTrue(all(len(response.items) == 1 for response in responses))
        friend_calls = [call for call in self.repository.calls if "friends" in call[0]]
        as_of_values = [
            call[2]
            for call in friend_calls
            if call[0].startswith("list-") and len(call) == 5
        ]
        self.assertTrue(as_of_values)
        self.assertTrue(
            all(value.tzinfo == timezone.utc for value in as_of_values)
        )


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


class RecordingNeoTransaction:
    def __init__(self, records):
        self.records = records
        self.calls = []

    async def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeNeoResult(self.records)


class RecommendationRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_artist_recommendations_use_period_weights_and_filter_friends(self):
        transaction = RecordingNeoTransaction(
            [
                {
                    "artistId": "artist_1",
                    "artistName": "Artist One",
                    "profilePictureUrl": None,
                    "spotifyUrl": None,
                    "users": [{"id": "usr_candidate", "username": "Candidate"}],
                }
            ]
        )

        buckets = await RecommendationNeoRepository.list_friend_recommendations_by_artists(
            transaction,
            "usr_current",
            "shortTermScore",
            skip=0,
            limit=10,
        )

        query, parameters = transaction.calls[0]
        self.assertEqual(buckets[0].users[0].id, "usr_candidate")
        self.assertIn("currentListen[$score_property]", query)
        self.assertIn("candidateAffinity DESC", query)
        self.assertIn("NOT EXISTS", query)
        self.assertIn("[0..20]", query)
        self.assertEqual(parameters["score_property"], "shortTermScore")

    async def test_friend_paths_use_decay_and_two_edge_product(self):
        transaction = RecordingNeoTransaction(
            [
                {
                    "friendId": "usr_friend",
                    "friendUsername": "Friend",
                    "users": [{"id": "usr_candidate", "username": "Candidate"}],
                }
            ]
        )
        as_of = datetime.now(timezone.utc)

        buckets = await RecommendationNeoRepository.list_friend_recommendations_by_friends(
            transaction,
            "usr_current",
            as_of,
            skip=0,
            limit=10,
        )

        query, parameters = transaction.calls[0]
        self.assertEqual(buckets[0].friend.id, "usr_friend")
        self.assertIn("/ 2592000.0", query)
        self.assertIn("friendCloseness * candidateCloseness", query)
        self.assertIn("pathScore DESC", query)
        self.assertEqual(parameters["as_of"], as_of)

    async def test_group_recommendations_exclude_memberships_and_map_tags(self):
        transaction = RecordingNeoTransaction(
            [
                {
                    "genreId": "genre_1",
                    "genreName": "Indie",
                    "groups": [
                        {
                            "id": "grp_1",
                            "ownerId": "usr_owner",
                            "name": "Indie Group",
                            "description": "A group",
                            "tags": [
                                {
                                    "labels": ["Artists"],
                                    "id": "artist_1",
                                    "name": "Artist One",
                                }
                            ],
                        }
                    ],
                }
            ]
        )

        buckets = await RecommendationNeoRepository.list_group_recommendations_by_genres(
            transaction,
            "usr_current",
            "longTermScore",
            skip=0,
            limit=10,
        )

        query, _ = transaction.calls[0]
        tag = buckets[0].groups[0].tags[0]
        self.assertIsInstance(tag, ArtistGroupTag)
        self.assertIn("NOT EXISTS", query)
        self.assertIn("MATCH (current)-[:PARTS_OF]->(group)", query)
        self.assertIn("currentAffinity DESC", query)
        self.assertIn("[0..20]", query)


if __name__ == "__main__":
    unittest.main()
