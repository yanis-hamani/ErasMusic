from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import Pagination


class FriendshipStatusEnum(str, Enum):
    friends = "friends"
    pending_incoming = "pending_incoming"
    pending_outgoing = "pending_outgoing"
    none = "none"


class FriendRequestStatusEnum(str, Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class FriendRequestDirection(str, Enum):
    incoming = "incoming"
    outgoing = "outgoing"
    all = "all"


class FriendSummary(BaseModel):
    id: str = Field(..., description="Unique user identifier", example="usr_a1b2c3d4e5f6")
    username: str = Field(..., description="User name", example="alex")


class PaginatedFriendsResponse(BaseModel):
    friends: list[FriendSummary]
    pagination: Pagination


class FriendshipStatus(BaseModel):
    userId: str = Field(..., description="Target user identifier", example="usr_456")
    status: FriendshipStatusEnum = Field(..., example="friends")


class FriendRequestCreate(BaseModel):
    targetUserId: str = Field(
        ...,
        min_length=1,
        description="User who should receive the request",
        example="usr_456",
    )


class FriendRequest(BaseModel):
    requestId: str = Field(..., description="Unique request identifier", example="req_789")
    senderId: str = Field(..., description="Request sender", example="usr_123")
    targetUserId: str = Field(..., description="Request recipient", example="usr_456")
    status: FriendRequestStatusEnum = Field(..., example="pending")
    createdAt: datetime = Field(..., description="Request creation time")


class PaginatedFriendRequestsResponse(BaseModel):
    requests: list[FriendRequest]
    pagination: Pagination
