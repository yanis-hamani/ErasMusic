from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional

# Request

class RegisterRequest(BaseModel) :
    username: str = Field(..., min_length=3, example="alex")
    email: EmailStr = Field(..., example="alex@example.com")
    password: str = Field(..., min_length=1, example="StrongPassword123")

class AuthLoginRequest(BaseModel):
    email: EmailStr = Field(..., example="alex@example.com")
    password: str = Field(..., min_length=1, example="StrongPassword123")

class RefreshRequest(BaseModel):
    refreshToken: Optional[str] = None

# Repositories
 
class RegisterHashed(BaseModel) :
    id: str = Field(..., description="Unique user identifier.", example="user_1")
    username: str = Field(..., min_length=3, example="alex")
    email: EmailStr = Field(..., example="alex@example.com")
    hashed_password: str = Field(..., min_length=1, example="aoziheaoigezoigezoghezoihgez")

class UserNeo(BaseModel):
    psql_id: str = Field(..., description="Unique user identifier.", example="user_1")
    username: str = Field(..., description="User name.", example="Alice")

class UserPsql(BaseModel):
    id: str = Field(..., description="Unique user identifier.", example="user_1")
    username: str = Field(..., description="User name.", example="Alice")
    email: EmailStr = Field(..., example="alex@example.com")
    avatar_url: HttpUrl | None = Field(
        default=None, 
        description="URL of the user's avatar image.", 
        example="https://example.com/avatar.jpg"
    )
    bio: str | None = Field(
        default=None, 
        max_length=500, 
        description="Short biography of the user.", 
        example="Software engineer and coffee enthusiast."
    )

class RefreshToken(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.", example="user_1")
    hashed_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    
# Response

class UserIdentity(BaseModel):
    id: str = Field(..., description="Unique user identifier.", example="user_1")
    username: str = Field(..., description="User name.", example="Alice")
    email: EmailStr = Field(..., example="alex@example.com")

class AuthTokenResponse(BaseModel):
    user: UserIdentity
    accessToken: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

class RefreshResponse(BaseModel):
    accessToken: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

class LogoutResponse(BaseModel):
    message: str = Field(default="Session terminated successfully")

