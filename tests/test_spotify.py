import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography.fernet import Fernet
from fastapi import status

from app.clients.spotify_client import SpotifyApiError, SpotifyClient
from app.core.token_encryption import TokenCipher, TokenEncryptionError
from app.models.spotify import SpotifySearchType
from app.repositories.spotify_neo_repository import SpotifyNeoRepository
from app.services.spotify_services import SpotifyService


class TokenCipherTests(unittest.TestCase):
    def test_tokens_are_encrypted_and_decrypted(self):
        key = Fernet.generate_key().decode("utf-8")
        with patch.dict(os.environ, {"SPOTIFY_TOKEN_ENCRYPTION_KEY": key}):
            cipher = TokenCipher()
        encrypted = cipher.encrypt("refresh-secret")
        self.assertNotEqual("refresh-secret", encrypted)
        self.assertEqual("refresh-secret", cipher.decrypt(encrypted))

    def test_missing_key_keeps_optional_integration_disabled(self):
        with patch.dict(os.environ, {"SPOTIFY_TOKEN_ENCRYPTION_KEY": ""}):
            cipher = TokenCipher()
        self.assertFalse(cipher.configured)
        with self.assertRaises(TokenEncryptionError):
            cipher.encrypt("secret")


class SpotifyClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_authorization_url_contains_state_scope_and_redirect(self):
        with patch.dict(
            os.environ,
            {
                "SPOTIFY_CLIENT_ID": "client-id",
                "SPOTIFY_CLIENT_SECRET": "client-secret",
                "SPOTIFY_REDIRECT_URI": "http://localhost:8000/spotify/callback",
            },
        ):
            client = SpotifyClient(httpx.AsyncClient())
        try:
            url = urlparse(client.authorization_url("state-value"))
            query = parse_qs(url.query)
            self.assertEqual(["state-value"], query["state"])
            self.assertEqual(["user-top-read user-read-private"], query["scope"])
            self.assertEqual(
                ["http://localhost:8000/spotify/callback"],
                query["redirect_uri"],
            )
        finally:
            await client._http.aclose()

    async def test_search_uses_client_credentials_and_current_limit(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/api/token":
                return httpx.Response(
                    200,
                    json={"access_token": "app-token", "expires_in": 3600},
                )
            return httpx.Response(
                200,
                json={"tracks": {"items": [], "total": 0}},
            )

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.dict(
            os.environ,
            {
                "SPOTIFY_CLIENT_ID": "client-id",
                "SPOTIFY_CLIENT_SECRET": "client-secret",
                "SPOTIFY_REDIRECT_URI": "http://localhost/callback",
            },
        ):
            client = SpotifyClient(http)
        try:
            await client.search("Muse", SpotifySearchType.track, 10, 0)
        finally:
            await http.aclose()
        search_request = requests[-1]
        self.assertEqual("10", search_request.url.params["limit"])
        self.assertEqual("Bearer app-token", search_request.headers["Authorization"])

    async def test_rate_limit_exposes_retry_after(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "7"}, json={})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = SpotifyClient(http)
        try:
            with self.assertRaises(SpotifyApiError) as context:
                await client.get_profile("token")
        finally:
            await http.aclose()
        self.assertEqual(429, context.exception.status_code)
        self.assertEqual(7, context.exception.retry_after)


class SpotifyPayloadTests(unittest.TestCase):
    def setUp(self):
        self.service = SpotifyService.__new__(SpotifyService)
        self.artist = {
            "id": "artist-1",
            "name": "Artist One",
            "images": [{"url": "https://example.com/artist.jpg"}],
            "external_urls": {"spotify": "https://open.spotify.com/artist/1"},
            "genres": ["Indie Rock"],
        }
        self.track = {
            "id": "track-1",
            "name": "Track One",
            "album": {"images": [{"url": "https://example.com/cover.jpg"}]},
            "external_urls": {"spotify": "https://open.spotify.com/track/1"},
            "artists": [
                {
                    "id": "artist-1",
                    "name": "Artist One",
                    "external_urls": {
                        "spotify": "https://open.spotify.com/artist/1"
                    },
                }
            ],
        }

    def test_rank_is_converted_to_fifty_down_to_one(self):
        responses = {}
        for period in ("short_term", "medium_term", "long_term"):
            responses[(period, "artists")] = [self.artist]
            responses[(period, "tracks")] = [self.track]
        periods, counts = self.service._build_sync_payloads(responses)
        self.assertEqual(50, periods["short_term"]["tracks"][0]["score"])
        self.assertEqual(50, periods["short_term"]["artists"][0]["score"])
        self.assertEqual("indie rock", periods["short_term"]["artists"][0]["genres"][0]["normalizedName"])
        self.assertEqual({"tracks": 1, "artists": 1, "genres": 1}, counts)

    def test_same_genre_name_has_stable_identifier(self):
        first = self.service._genre_data(" Indie   Rock ")
        second = self.service._genre_data("indie rock")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual("indie rock", first["normalizedName"])

    def test_local_and_missing_ids_are_skipped_without_changing_rank(self):
        local_track = {**self.track, "id": None, "is_local": True}
        missing_artist = {**self.artist, "id": None}
        responses = {}
        for period in ("short_term", "medium_term", "long_term"):
            responses[(period, "artists")] = [missing_artist, self.artist]
            responses[(period, "tracks")] = [local_track, self.track]

        periods, counts = self.service._build_sync_payloads(responses)

        self.assertEqual(49, periods["short_term"]["tracks"][0]["score"])
        self.assertEqual(49, periods["short_term"]["artists"][0]["score"])
        self.assertEqual({"tracks": 1, "artists": 1, "genres": 1}, counts)

    def test_upstream_unavailable_remains_service_unavailable(self):
        error = self.service._http_error(SpotifyApiError(503, "Spotify is unavailable"))
        self.assertEqual(status.HTTP_503_SERVICE_UNAVAILABLE, error.status_code)


class RecordingResult:
    async def consume(self):
        return None


class RecordingTransaction:
    def __init__(self):
        self.calls = []

    async def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return RecordingResult()


class SpotifyNeoRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_period_sync_replaces_scores_and_merges_direct_artist_affinity(self):
        transaction = RecordingTransaction()
        await SpotifyNeoRepository.replace_period_affinities(
            transaction,
            "usr_1",
            "short_term",
            tracks=[],
            artists=[],
        )
        query = "\n".join(call[0] for call in transaction.calls)
        self.assertIn("listen.shortTermScore = 0", query)
        self.assertIn("preference.shortTermScore = item.score", query)
        self.assertIn("TOP_ARTIST", query)
        self.assertIn("normalizedName", query)


class LoginSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_daily_sync_failure_is_never_raised_to_login(self):
        service = SpotifyService.__new__(SpotifyService)
        service.spotify_client = type("Client", (), {"configured": True})()
        service.token_cipher = type("Cipher", (), {"configured": True})()
        service._synchronize = AsyncMock(side_effect=SpotifyApiError(503, "offline"))
        await service.synchronize_after_login("usr_1")
        service._synchronize.assert_awaited_once_with(
            "usr_1",
            force=False,
            manual=False,
        )


if __name__ == "__main__":
    unittest.main()
