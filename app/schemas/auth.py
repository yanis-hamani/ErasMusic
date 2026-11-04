from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class AuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, example="alex")
    email: EmailStr = Field(..., example="alex@example.com")
    password: str = Field(..., min_length=1, example="StrongPassword123")

class AuthLoginRequest(BaseModel):
    email: EmailStr = Field(..., example="alex@example.com")
    password: str = Field(..., min_length=1, example="StrongPassword123")

class UserIdentity(BaseModel):
    id: str = Field(..., example="user_123")
    username: str = Field(..., example="alex")
    email: EmailStr = Field(..., example="alex@example.com")

class AuthTokenResponse(BaseModel):
    user: UserIdentity
    accessToken: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

class RefreshRequest(BaseModel):
    refreshToken: Optional[str] = None

class RefreshResponse(BaseModel):
    accessToken: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

class LogoutResponse(BaseModel):
    message: str = Field(default="Session terminated successfully")
