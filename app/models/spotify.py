from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.music import Artist, Song


class SpotifySearchType(str, Enum):
    track = "track"
    artist = "artist"


class SpotifyTokenData(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    scope: str = ""


class SpotifyConnectionRecord(BaseModel):
    user_id: str
    spotify_user_id: str
    access_token_encrypted: str
    refresh_token_encrypted: str
    access_token_expires_at: datetime
    scopes: str
    connected_at: datetime
    last_successful_sync_at: datetime | None = None
    sync_started_at: datetime | None = None
    last_sync_error: str | None = None
    reconnect_required: bool = False


class SpotifyConnectResponse(BaseModel):
    authorizationUrl: str = Field(
        ...,
        description="URL the client must open to authorize Spotify",
    )
    expiresAt: datetime = Field(..., description="Expiration time of the OAuth state")


class SpotifyConnectionStatus(BaseModel):
    connected: bool
    spotifyUserId: str | None = None
    lastSuccessfulSyncAt: datetime | None = None
    syncInProgress: bool = False
    reconnectRequired: bool = False
    lastSyncError: str | None = None


class SpotifySyncResponse(BaseModel):
    status: str = "synchronized"
    tracks: int = Field(..., ge=0, description="Distinct synchronized tracks")
    artists: int = Field(..., ge=0, description="Distinct synchronized artists")
    genres: int = Field(..., ge=0, description="Distinct synchronized genres")
    syncedAt: datetime


class SpotifySearchResponse(BaseModel):
    type: SpotifySearchType
    tracks: list[Song] = Field(default_factory=list)
    artists: list[Artist] = Field(default_factory=list)
    limit: int = Field(..., ge=1, le=10)
    offset: int = Field(..., ge=0)
    total: int = Field(..., ge=0)
