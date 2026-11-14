import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import HTTPException, status
from neo4j import AsyncDriver

from app.clients.spotify_client import (
    SpotifyApiError,
    SpotifyClient,
    SpotifyConfigurationError,
)
from app.core.token_encryption import TokenCipher, TokenEncryptionError
from app.models.music import Artist, Song
from app.models.recommendations import RecommendationPeriod
from app.models.spotify import (
    SpotifyConnectResponse,
    SpotifyConnectionRecord,
    SpotifyConnectionStatus,
    SpotifySearchResponse,
    SpotifySearchType,
    SpotifySyncResponse,
    SpotifyTokenData,
)
from app.repositories.spotify_neo_repository import SpotifyNeoRepository
from app.repositories.spotify_psql_repository import SpotifyPsqlRepository


logger = logging.getLogger(__name__)


class SpotifyService:
    OAUTH_STATE_LIFETIME = timedelta(minutes=10)

    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        neo4j_driver: AsyncDriver,
        spotify_client: SpotifyClient,
        token_cipher: TokenCipher,
        spotify_psql_repository: SpotifyPsqlRepository,
        spotify_neo_repository: SpotifyNeoRepository,
    ):
        self.pg_pool = pg_pool
        self.neo4j_driver = neo4j_driver
        self.spotify_client = spotify_client
        self.token_cipher = token_cipher
        self.spotify_psql_repository = spotify_psql_repository
        self.spotify_neo_repository = spotify_neo_repository

    def _require_configured(self) -> None:
        try:
            self.spotify_client.require_configured()
            if not self.token_cipher.configured:
                raise TokenEncryptionError(
                    "SPOTIFY_TOKEN_ENCRYPTION_KEY is not configured"
                )
        except (SpotifyConfigurationError, TokenEncryptionError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error

    async def create_authorization(self, user_id: str) -> SpotifyConnectResponse:
        self._require_configured()
        state_value = secrets.token_urlsafe(32)
        state_hash = self._hash_state(state_value)
        expires_at = datetime.now(timezone.utc) + self.OAUTH_STATE_LIFETIME
        async with self.pg_pool.acquire() as connection:
            await self.spotify_psql_repository.create_oauth_state(
                connection,
                state_hash,
                user_id,
                expires_at,
            )
        return SpotifyConnectResponse(
            authorizationUrl=self.spotify_client.authorization_url(state_value),
            expiresAt=expires_at,
        )

    async def complete_authorization(
        self,
        state_value: str,
        code: str | None,
        oauth_error: str | None,
    ) -> SpotifyConnectionStatus:
        self._require_configured()
        async with self.pg_pool.acquire() as connection:
            user_id = await self.spotify_psql_repository.consume_oauth_state(
                connection,
                self._hash_state(state_value),
            )
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Spotify authorization state is invalid or expired",
            )
        if oauth_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Spotify authorization was not completed: {oauth_error}",
            )
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Spotify authorization code is missing",
            )

        try:
            token = await self.spotify_client.exchange_code(code)
            if not token.refresh_token:
                raise SpotifyApiError(502, "Spotify did not return a refresh token")
            profile = await self.spotify_client.get_profile(token.access_token)
            spotify_user_id = profile.get("id")
            if not spotify_user_id:
                raise SpotifyApiError(502, "Spotify profile has no user identifier")
            now = datetime.now(timezone.utc)
            record = SpotifyConnectionRecord(
                user_id=user_id,
                spotify_user_id=spotify_user_id,
                access_token_encrypted=self.token_cipher.encrypt(token.access_token),
                refresh_token_encrypted=self.token_cipher.encrypt(token.refresh_token),
                access_token_expires_at=now + timedelta(seconds=token.expires_in),
                scopes=token.scope,
                connected_at=now,
            )
            async with self.pg_pool.acquire() as connection:
                await self.spotify_psql_repository.upsert_connection(
                    connection,
                    record,
                )
        except asyncpg.UniqueViolationError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Spotify account is already linked to another user",
            ) from error
        except (SpotifyApiError, TokenEncryptionError) as error:
            raise self._http_error(error) from error

        try:
            await self._synchronize(user_id, force=True, manual=False)
        except Exception as error:
            logger.warning("Initial Spotify sync failed for %s: %s", user_id, error)
        return await self.get_status(user_id)

    async def get_status(self, user_id: str) -> SpotifyConnectionStatus:
        async with self.pg_pool.acquire() as connection:
            record = await self.spotify_psql_repository.select_connection(
                connection,
                user_id,
            )
        if record is None:
            return SpotifyConnectionStatus(connected=False)
        now = datetime.now(timezone.utc)
        sync_in_progress = bool(
            record.sync_started_at
            and record.sync_started_at >= now - timedelta(minutes=15)
        )
        return SpotifyConnectionStatus(
            connected=True,
            spotifyUserId=record.spotify_user_id,
            lastSuccessfulSyncAt=record.last_successful_sync_at,
            syncInProgress=sync_in_progress,
            reconnectRequired=record.reconnect_required,
            lastSyncError=record.last_sync_error,
        )

    async def synchronize(self, user_id: str) -> SpotifySyncResponse:
        self._require_configured()
        result = await self._synchronize(user_id, force=True, manual=True)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Spotify synchronization is already running",
            )
        return result

    async def synchronize_after_login(self, user_id: str) -> None:
        if not self.spotify_client.configured or not self.token_cipher.configured:
            return
        try:
            await self._synchronize(user_id, force=False, manual=False)
        except Exception as error:
            logger.warning("Daily Spotify sync failed for %s: %s", user_id, error)

    async def disconnect(self, user_id: str) -> None:
        async with self.pg_pool.acquire() as connection:
            async with connection.transaction():
                deleted = await self.spotify_psql_repository.delete_connection(
                    connection,
                    user_id,
                )
                if not deleted:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Spotify connection not found",
                    )

                async def delete_affinities(transaction):
                    await self.spotify_neo_repository.delete_user_affinities(
                        transaction,
                        user_id,
                    )

                async with self.neo4j_driver.session() as session:
                    await session.execute_write(delete_affinities)

    async def search(
        self,
        query: str,
        item_type: SpotifySearchType,
        limit: int,
        offset: int,
    ) -> SpotifySearchResponse:
        self._require_configured()
        try:
            payload = await self.spotify_client.search(
                query.strip(),
                item_type,
                limit,
                offset,
            )
        except SpotifyApiError as error:
            raise self._http_error(error) from error

        if item_type == SpotifySearchType.artist:
            page = payload.get("artists") or {}
            artists = [
                self._artist_model(item)
                for item in page.get("items") or []
                if self._has_spotify_id(item)
            ]
            return SpotifySearchResponse(
                type=item_type,
                artists=artists,
                limit=limit,
                offset=offset,
                total=int(page.get("total") or 0),
            )

        page = payload.get("tracks") or {}
        tracks = [
            self._song_model(item)
            for item in page.get("items") or []
            if not item.get("is_local") and self._has_spotify_id(item)
        ]
        return SpotifySearchResponse(
            type=item_type,
            tracks=tracks,
            limit=limit,
            offset=offset,
            total=int(page.get("total") or 0),
        )

    async def _synchronize(
        self,
        user_id: str,
        force: bool,
        manual: bool,
    ) -> SpotifySyncResponse | None:
        now = datetime.now(timezone.utc)
        async with self.pg_pool.acquire() as connection:
            existing = await self.spotify_psql_repository.select_connection(
                connection,
                user_id,
            )
            if existing is None:
                if manual:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Spotify account is not connected",
                    )
                return None
            if existing.reconnect_required:
                if manual:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Spotify authorization must be renewed",
                    )
                return None
            record = await self.spotify_psql_repository.claim_sync(
                connection,
                user_id,
                now,
                now.date(),
                force,
            )
        if record is None:
            return None

        try:
            access_token, record = await self._valid_access_token(record)
            try:
                responses = await self._fetch_top_items(access_token)
            except SpotifyApiError as error:
                if error.status_code != 401:
                    raise
                access_token, record = await self._refresh_connection(record)
                responses = await self._fetch_top_items(access_token)

            periods, distinct_counts = self._build_sync_payloads(responses)

            async def write_graph(transaction):
                for period in RecommendationPeriod:
                    payload = periods[period.value]
                    await self.spotify_neo_repository.replace_period_affinities(
                        transaction,
                        user_id,
                        period.value,
                        payload["tracks"],
                        payload["artists"],
                    )
                await self.spotify_neo_repository.cleanup_empty_affinities(
                    transaction,
                    user_id,
                )

            async with self.neo4j_driver.session() as session:
                await session.execute_write(write_graph)

            synced_at = datetime.now(timezone.utc)
            async with self.pg_pool.acquire() as connection:
                await self.spotify_psql_repository.complete_sync(
                    connection,
                    user_id,
                    synced_at,
                )
            return SpotifySyncResponse(
                tracks=distinct_counts["tracks"],
                artists=distinct_counts["artists"],
                genres=distinct_counts["genres"],
                syncedAt=synced_at,
            )
        except Exception as error:
            reconnect_required = isinstance(error, SpotifyApiError) and error.status_code in {
                400,
                401,
            }
            async with self.pg_pool.acquire() as connection:
                await self.spotify_psql_repository.fail_sync(
                    connection,
                    user_id,
                    str(error),
                    reconnect_required=reconnect_required,
                )
            if manual:
                if isinstance(error, (SpotifyApiError, TokenEncryptionError)):
                    raise self._http_error(error) from error
                if isinstance(error, HTTPException):
                    raise
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Spotify synchronization failed",
                ) from error
            raise

    async def _valid_access_token(
        self,
        record: SpotifyConnectionRecord,
    ) -> tuple[str, SpotifyConnectionRecord]:
        if record.access_token_expires_at > datetime.now(timezone.utc) + timedelta(
            seconds=60
        ):
            return self.token_cipher.decrypt(record.access_token_encrypted), record
        return await self._refresh_connection(record)

    async def _refresh_connection(
        self,
        record: SpotifyConnectionRecord,
    ) -> tuple[str, SpotifyConnectionRecord]:
        refresh_token = self.token_cipher.decrypt(record.refresh_token_encrypted)
        token = await self.spotify_client.refresh_token(refresh_token)
        new_refresh_token = token.refresh_token or refresh_token
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token.expires_in)
        access_encrypted = self.token_cipher.encrypt(token.access_token)
        refresh_encrypted = self.token_cipher.encrypt(new_refresh_token)
        async with self.pg_pool.acquire() as connection:
            await self.spotify_psql_repository.update_tokens(
                connection,
                record.user_id,
                access_encrypted,
                refresh_encrypted,
                expires_at,
                token.scope,
            )
        updated = record.model_copy(
            update={
                "access_token_encrypted": access_encrypted,
                "refresh_token_encrypted": refresh_encrypted,
                "access_token_expires_at": expires_at,
                "scopes": token.scope or record.scopes,
            }
        )
        return token.access_token, updated

    async def _fetch_top_items(self, access_token: str) -> dict:
        tasks = {}
        for period in RecommendationPeriod:
            tasks[(period.value, "tracks")] = self.spotify_client.get_top_items(
                access_token,
                "tracks",
                period.value,
            )
            tasks[(period.value, "artists")] = self.spotify_client.get_top_items(
                access_token,
                "artists",
                period.value,
            )
        values = await asyncio.gather(*tasks.values())
        return dict(zip(tasks, values))

    def _build_sync_payloads(self, responses: dict) -> tuple[dict, dict[str, int]]:
        artist_catalog = {}
        for period in RecommendationPeriod:
            for item in responses[(period.value, "artists")]:
                if not self._has_spotify_id(item):
                    continue
                artist_catalog[item["id"]] = self._artist_data(item, score=0)

        periods = {}
        all_track_ids = set()
        all_artist_ids = set(artist_catalog)
        all_genre_ids = set()
        for period in RecommendationPeriod:
            artists = []
            for rank, item in enumerate(
                responses[(period.value, "artists")],
                start=1,
            ):
                if not self._has_spotify_id(item):
                    continue
                artist = self._artist_data(item, score=51 - rank)
                artists.append(artist)
                all_genre_ids.update(genre["id"] for genre in artist["genres"])

            tracks = []
            for rank, item in enumerate(
                responses[(period.value, "tracks")],
                start=1,
            ):
                if item.get("is_local") or not self._has_spotify_id(item):
                    continue
                track = self._track_data(
                    item,
                    score=51 - rank,
                    artist_catalog=artist_catalog,
                )
                tracks.append(track)
                all_track_ids.add(track["id"])
                all_artist_ids.update(artist["id"] for artist in track["artists"])
                all_genre_ids.update(genre["id"] for genre in track["genres"])
            periods[period.value] = {"tracks": tracks, "artists": artists}

        return periods, {
            "tracks": len(all_track_ids),
            "artists": len(all_artist_ids),
            "genres": len(all_genre_ids),
        }

    def _artist_data(self, item: dict, score: int) -> dict:
        genres = [
            self._genre_data(name)
            for name in item.get("genres") or []
            if name and name.strip()
        ]
        return {
            "id": item["id"],
            "name": item.get("name") or "Unknown artist",
            "profilePictureUrl": self._first_image(item.get("images")),
            "spotifyUrl": (item.get("external_urls") or {}).get("spotify"),
            "genres": genres,
            "score": score,
        }

    def _track_data(
        self,
        item: dict,
        score: int,
        artist_catalog: dict,
    ) -> dict:
        artists = []
        genre_map = {}
        for artist_item in item.get("artists") or []:
            if not self._has_spotify_id(artist_item):
                continue
            enriched = artist_catalog.get(artist_item.get("id"))
            if enriched:
                artist = {
                    key: enriched[key]
                    for key in (
                        "id",
                        "name",
                        "profilePictureUrl",
                        "spotifyUrl",
                    )
                }
                for genre in enriched["genres"]:
                    genre_map[genre["id"]] = genre
            else:
                artist = {
                    "id": artist_item["id"],
                    "name": artist_item.get("name") or "Unknown artist",
                    "profilePictureUrl": None,
                    "spotifyUrl": (artist_item.get("external_urls") or {}).get(
                        "spotify"
                    ),
                }
            artists.append(artist)
        album = item.get("album") or {}
        return {
            "id": item["id"],
            "title": item.get("name") or "Unknown track",
            "coverUrl": self._first_image(album.get("images")),
            "spotifyUrl": (item.get("external_urls") or {}).get("spotify"),
            "artists": artists,
            "genres": list(genre_map.values()),
            "score": score,
        }

    @staticmethod
    def _genre_data(name: str) -> dict:
        normalized = " ".join(name.casefold().split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return {
            "id": f"genre_{digest}",
            "name": name.strip(),
            "normalizedName": normalized,
        }

    @staticmethod
    def _first_image(images) -> str | None:
        if not images:
            return None
        return images[0].get("url")

    def _artist_model(self, item: dict) -> Artist:
        return Artist(
            id=item["id"],
            name=item.get("name") or "Unknown artist",
            profilePictureUrl=self._first_image(item.get("images")),
            spotifyUrl=(item.get("external_urls") or {}).get("spotify"),
        )

    def _song_model(self, item: dict) -> Song:
        artists = [
            self._artist_model(artist)
            for artist in item.get("artists") or []
            if self._has_spotify_id(artist)
        ]
        return Song(
            id=item["id"],
            title=item.get("name") or "Unknown track",
            coverUrl=self._first_image((item.get("album") or {}).get("images")),
            spotifyUrl=(item.get("external_urls") or {}).get("spotify"),
            artists=artists,
        )

    @staticmethod
    def _hash_state(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _has_spotify_id(item: dict) -> bool:
        return isinstance(item.get("id"), str) and bool(item["id"].strip())

    @staticmethod
    def _http_error(error: Exception) -> HTTPException:
        if isinstance(error, SpotifyConfigurationError):
            return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))
        if isinstance(error, TokenEncryptionError):
            return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))
        if isinstance(error, SpotifyApiError):
            if error.status_code == 429:
                headers = (
                    {"Retry-After": str(error.retry_after)}
                    if error.retry_after is not None
                    else None
                )
                return HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Spotify rate limit exceeded",
                    headers=headers,
                )
            if error.status_code in {400, 401}:
                return HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Spotify authorization must be renewed",
                )
            if error.status_code == 403:
                return HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    str(error),
                )
            if error.status_code == 503:
                return HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    str(error),
                )
            return HTTPException(status.HTTP_502_BAD_GATEWAY, str(error))
        return HTTPException(status.HTTP_502_BAD_GATEWAY, str(error))
