import unittest

from fastapi import HTTPException

from app.models.music import Artist, Genre, Song
from app.repositories.music_neo_repository import MusicNeoRepository
from app.services.music_services import MusicService


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


class FakeMusicRepository:
    def __init__(self):
        self.artist = Artist(
            id="artist_1",
            name="Artist One",
            profilePictureUrl="https://example.com/artist.jpg",
            spotifyUrl="https://open.spotify.com/artist/1",
        )
        self.song = Song(
            id="song_1",
            title="First Song",
            coverUrl="https://example.com/cover.jpg",
            spotifyUrl="https://open.spotify.com/track/1",
            artists=[self.artist],
        )
        self.genre = Genre(id="genre_1", name="Indie")
        self.artist_total = 11
        self.song_total = 0
        self.genre_total = 1
        self.artist_page = None
        self.song_page = None
        self.genre_page = None

    async def count_artists(self, transaction):
        return self.artist_total

    async def list_artists(self, transaction, skip, limit):
        self.artist_page = (skip, limit)
        return [self.artist]

    async def select_artist(self, transaction, artist_id):
        return self.artist if artist_id == self.artist.id else None

    async def count_songs(self, transaction):
        return self.song_total

    async def list_songs(self, transaction, skip, limit):
        self.song_page = (skip, limit)
        return [] if self.song_total == 0 else [self.song]

    async def select_song(self, transaction, song_id):
        return self.song if song_id == self.song.id else None

    async def count_genres(self, transaction):
        return self.genre_total

    async def list_genres(self, transaction, skip, limit):
        self.genre_page = (skip, limit)
        return [self.genre]

    async def select_genre(self, transaction, genre_id):
        return self.genre if genre_id == self.genre.id else None


class MusicServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeMusicRepository()
        self.service = MusicService(FakeDriver(), self.repository)

    async def test_artist_listing_is_paginated(self):
        response = await self.service.list_artists(page=2, limit=10)

        self.assertEqual(response.artists[0].id, "artist_1")
        self.assertEqual(self.repository.artist_page, (10, 10))
        self.assertEqual(response.pagination.totalItems, 11)
        self.assertEqual(response.pagination.totalPages, 2)

    async def test_empty_song_listing_has_zero_pages(self):
        response = await self.service.list_songs(page=1, limit=10)

        self.assertEqual(response.songs, [])
        self.assertEqual(self.repository.song_page, (0, 10))
        self.assertEqual(response.pagination.totalPages, 0)

    async def test_genre_listing_is_paginated(self):
        response = await self.service.list_genres(page=1, limit=5)

        self.assertEqual(response.genres, [self.repository.genre])
        self.assertEqual(self.repository.genre_page, (0, 5))

    async def test_get_operations_return_catalog_entities(self):
        artist = await self.service.get_artist("artist_1")
        song = await self.service.get_song("song_1")
        genre = await self.service.get_genre("genre_1")

        self.assertEqual(artist, self.repository.artist)
        self.assertEqual(song, self.repository.song)
        self.assertEqual(genre, self.repository.genre)

    async def test_missing_entities_return_specific_404_errors(self):
        operations = [
            (self.service.get_artist("missing"), "Artist not found"),
            (self.service.get_song("missing"), "Song not found"),
            (self.service.get_genre("missing"), "Genre not found"),
        ]

        for operation, detail in operations:
            with self.subTest(detail=detail):
                with self.assertRaises(HTTPException) as raised:
                    await operation
                self.assertEqual(raised.exception.status_code, 404)
                self.assertEqual(raised.exception.detail, detail)


class MusicRepositoryMappingTests(unittest.TestCase):
    def test_artist_empty_urls_are_normalized_to_null(self):
        artist = MusicNeoRepository._artist(
            {
                "id": "artist_1",
                "name": "Artist One",
                "profilePictureUrl": "",
                "spotifyUrl": None,
            }
        )

        self.assertIsNone(artist.profilePictureUrl)
        self.assertIsNone(artist.spotifyUrl)

    def test_song_without_relationships_has_empty_artists(self):
        song = MusicNeoRepository._song(
            {
                "id": "song_1",
                "title": "Orphan Song",
                "coverUrl": None,
                "spotifyUrl": None,
                "artists": [],
            }
        )

        self.assertEqual(song.artists, [])

    def test_song_maps_all_performing_artists(self):
        song = MusicNeoRepository._song(
            {
                "id": "song_1",
                "title": "Collaboration",
                "coverUrl": "https://example.com/cover.jpg",
                "spotifyUrl": "https://open.spotify.com/track/1",
                "artists": [
                    {
                        "id": "artist_1",
                        "name": "Artist One",
                        "profilePictureUrl": None,
                        "spotifyUrl": None,
                    },
                    {
                        "id": "artist_2",
                        "name": "Artist Two",
                        "profilePictureUrl": None,
                        "spotifyUrl": None,
                    },
                ],
            }
        )

        self.assertEqual(
            [artist.id for artist in song.artists],
            ["artist_1", "artist_2"],
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


class FakeNeoTransaction:
    def __init__(self):
        self.calls = []

    async def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeNeoResult(
            [
                {
                    "id": "song_1",
                    "title": "Orphan Song",
                    "coverUrl": None,
                    "spotifyUrl": None,
                    "artists": [],
                }
            ]
        )


class StaticNeoTransaction:
    def __init__(self, records):
        self.records = records
        self.calls = []

    async def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeNeoResult(self.records)


class MusicRepositoryQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_artist_and_genre_lists_use_alphabetical_id_ordering(self):
        artist_transaction = StaticNeoTransaction(
            [
                {
                    "id": "artist_1",
                    "name": "Artist One",
                    "profilePictureUrl": None,
                    "spotifyUrl": None,
                }
            ]
        )
        genre_transaction = StaticNeoTransaction(
            [{"id": "genre_1", "name": "Indie"}]
        )

        await MusicNeoRepository.list_artists(artist_transaction, skip=0, limit=10)
        await MusicNeoRepository.list_genres(genre_transaction, skip=0, limit=10)

        self.assertIn(
            "ORDER BY toLower(artist.name), artist.id",
            artist_transaction.calls[0][0],
        )
        self.assertIn(
            "ORDER BY toLower(genre.name), genre.id",
            genre_transaction.calls[0][0],
        )

    async def test_song_page_is_selected_before_artist_expansion(self):
        transaction = FakeNeoTransaction()

        songs = await MusicNeoRepository.list_songs(
            transaction,
            skip=10,
            limit=5,
        )

        query, parameters = transaction.calls[0]
        self.assertEqual(songs[0].artists, [])
        self.assertLess(query.index("SKIP $skip"), query.index("OPTIONAL MATCH"))
        self.assertIn("collect(DISTINCT", query)
        self.assertIn("ORDER BY toLower(artist.name), artist.id", query)
        self.assertIn("ORDER BY toLower(song.title), song.id", query)
        self.assertEqual(parameters, {"skip": 10, "limit": 5})


if __name__ == "__main__":
    unittest.main()
