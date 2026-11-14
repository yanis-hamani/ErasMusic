import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from urllib.parse import urlencode

import httpx

from app.models.spotify import SpotifySearchType, SpotifyTokenData


SPOTIFY_SCOPES = "user-top-read user-read-private"


class SpotifyConfigurationError(RuntimeError):
    pass


class SpotifyApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        message: str,
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class SpotifyClient:
    accounts_url = "https://accounts.spotify.com"
    api_url = "https://api.spotify.com/v1"

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self.client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "").strip()
        self._http = http_client or httpx.AsyncClient(timeout=20.0)
        self._owns_http_client = http_client is None
        self._application_token: str | None = None
        self._application_token_expires_at: datetime | None = None
        self._application_token_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def require_configured(self) -> None:
        if not self.configured:
            raise SpotifyConfigurationError(
                "Spotify integration requires client ID, client secret, and redirect URI"
            )

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http.aclose()

    def authorization_url(self, state: str) -> str:
        self.require_configured()
        query = urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": SPOTIFY_SCOPES,
                "state": state,
            }
        )
        return f"{self.accounts_url}/authorize?{query}"

    async def exchange_code(self, code: str) -> SpotifyTokenData:
        self.require_configured()
        try:
            response = await self._http.post(
                f"{self.accounts_url}/api/token",
                auth=(self.client_id, self.client_secret),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.RequestError as error:
            raise SpotifyApiError(503, "Spotify is unavailable") from error
        return self._token_response(response)

    async def refresh_token(self, refresh_token: str) -> SpotifyTokenData:
        self.require_configured()
        try:
            response = await self._http.post(
                f"{self.accounts_url}/api/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.RequestError as error:
            raise SpotifyApiError(503, "Spotify is unavailable") from error
        return self._token_response(response)

    async def get_profile(self, access_token: str) -> dict:
        return await self._get("/me", access_token)

    async def get_top_items(
        self,
        access_token: str,
        item_type: str,
        time_range: str,
    ) -> list[dict]:
        payload = await self._get(
            f"/me/top/{item_type}",
            access_token,
            params={"time_range": time_range, "limit": 50, "offset": 0},
        )
        return list(payload.get("items") or [])

    async def search(
        self,
        query: str,
        item_type: SpotifySearchType,
        limit: int,
        offset: int,
    ) -> dict:
        token = await self._get_application_token()
        return await self._get(
            "/search",
            token,
            params={
                "q": query,
                "type": item_type.value,
                "limit": limit,
                "offset": offset,
            },
        )

    async def _get_application_token(self) -> str:
        self.require_configured()
        now = datetime.now(timezone.utc)
        if (
            self._application_token
            and self._application_token_expires_at
            and self._application_token_expires_at > now + timedelta(seconds=60)
        ):
            return self._application_token

        async with self._application_token_lock:
            now = datetime.now(timezone.utc)
            if (
                self._application_token
                and self._application_token_expires_at
                and self._application_token_expires_at > now + timedelta(seconds=60)
            ):
                return self._application_token
            try:
                response = await self._http.post(
                    f"{self.accounts_url}/api/token",
                    auth=(self.client_id, self.client_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.RequestError as error:
                raise SpotifyApiError(503, "Spotify is unavailable") from error
            token = self._token_response(response)
            self._application_token = token.access_token
            self._application_token_expires_at = now + timedelta(
                seconds=token.expires_in
            )
            return token.access_token

    async def _get(
        self,
        path: str,
        access_token: str,
        params: dict | None = None,
    ) -> dict:
        try:
            response = await self._http.get(
                f"{self.api_url}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
        except httpx.RequestError as error:
            raise SpotifyApiError(503, "Spotify is unavailable") from error
        if response.is_error:
            self._raise_api_error(response)
        return response.json()

    def _token_response(self, response: httpx.Response) -> SpotifyTokenData:
        if response.is_error:
            self._raise_api_error(response)
        payload = response.json()
        return SpotifyTokenData(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_in=int(payload["expires_in"]),
            scope=payload.get("scope") or "",
        )

    @staticmethod
    def _raise_api_error(response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error", payload)
        if isinstance(error, dict):
            message = error.get("message") or error.get("error_description")
        else:
            message = str(error)
        retry_value = response.headers.get("Retry-After")
        retry_after = int(retry_value) if retry_value and retry_value.isdigit() else None
        raise SpotifyApiError(
            response.status_code,
            message or "Spotify request failed",
            retry_after,
        )


async def init_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
    client = SpotifyClient()
    try:
        yield client
    finally:
        await client.close()
