from pydantic import BaseModel, Field
from typing import List
from enum import Enum
from datetime import datetime

# Enums

class FriendshipStatusEnum(str, Enum):
    friends = "friends"
    pending_incoming = "pending_incoming"
    pending_outgoing = "pending_outgoing"
    none = "none"

class FriendRequestStatusEnum(str, Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"

class DirectionEnum(str, Enum):
    incoming = "incoming"
    outgoing = "outgoing"
    all = "all"

# Models

class User(BaseModel):
    id: str = Field(..., description="Unique user identifier.", example="user_1")
    name: str = Field(..., description="User name.", example="Alice")

class Pagination(BaseModel):
    page: int = Field(..., ge=1, description="Current page number", example=2)
    limit: int = Field(..., ge=1, description="Maximum number of items per page", example=20)
    totalItems: int = Field(..., ge=0, description="Total number of items available", example=95)
    totalPages: int = Field(..., ge=0, description="Total number of pages available", example=5)

class PaginatedFriendsResponse(BaseModel):
    friends: List[User]
    pagination: Pagination

class FriendshipStatus(BaseModel):
    userId: str = Field(..., example="usr_456")
    status: FriendshipStatusEnum = Field(..., example="friends")

class FriendRequestCreate(BaseModel):
    targetUserId: str = Field(..., example="usr_456")

class FriendRequest(BaseModel):
    requestId: str = Field(..., example="req_789")
    senderId: str = Field(..., example="usr_123")
    targetUserId: str = Field(..., example="usr_456")
    status: FriendRequestStatusEnum = Field(..., example="pending")
    createdAt: datetime
