from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# Request

class RegisterRequest(BaseModel) :
    username: str = Field(..., min_length=3, description="Unique user name", example="alex")
    email: EmailStr = Field(..., description="Unique email address", example="alex@example.com")
    password: str = Field(
        ...,
        min_length=1,
        description="Account password",
        example="StrongPassword123",
        json_schema_extra={"format": "password"},
    )

class AuthLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Account email address", example="alex@example.com")
    password: str = Field(
        ...,
        min_length=1,
        description="Account password",
        example="StrongPassword123",
        json_schema_extra={"format": "password"},
    )

class RefreshRequest(BaseModel):
    refreshToken: Optional[str] = Field(
        default=None,
        description="Optional fallback when the refresh_token cookie is absent",
    )

# Repositories
 
class RegisterHashed(BaseModel) :
    id: str = Field(..., description="Unique user identifier.", example="user_1")
    username: str = Field(..., min_length=3, example="alex")
    email: EmailStr = Field(..., example="alex@example.com")
    hashed_password: str = Field(..., min_length=1, example="aoziheaoigezoigezoghezoihgez")

class UserNeo(BaseModel):
    psql_id: str = Field(..., description="Unique user identifier.", example="user_1")
    username: str = Field(..., description="User name.", example="Alice")

class RefreshToken(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.", example="user_1")
    hashed_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    
# Response

class UserIdentity(BaseModel):
    id: str = Field(..., description="Unique user identifier.", example="usr_a1b2c3d4e5f6")
    username: str = Field(..., min_length=3, description="User name.", example="alex")
    email: EmailStr = Field(..., description="Account email address", example="alex@example.com")

class AuthTokenResponse(BaseModel):
    user: UserIdentity
    accessToken: str = Field(
        ...,
        description="Bearer access token",
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    )

class RefreshResponse(BaseModel):
    accessToken: str = Field(
        ...,
        description="New bearer access token",
        example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    )

class LogoutResponse(BaseModel):
    message: str = Field(
        default="Session terminated successfully",
        description="Logout confirmation",
        example="Session terminated successfully",
    )
