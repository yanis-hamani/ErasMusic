from pydantic import BaseModel, EmailStr, Field, HttpUrl, model_validator


class UserRecord(BaseModel):
    """Internal representation of a user stored in PostgreSQL."""

    id: str
    username: str
    email: EmailStr
    avatar_url: HttpUrl | None = None
    bio: str | None = Field(default=None, max_length=500)


class PublicUserProfile(BaseModel):
    id: str = Field(..., description="Unique user identifier.", example="usr_a1b2c3d4e5f6")
    username: str = Field(..., description="User name.", example="alex")
    avatarUrl: HttpUrl | None = Field(
        default=None,
        description="URL of the user's avatar image.",
        example="https://example.com/avatar.jpg",
    )
    bio: str | None = Field(
        default=None,
        max_length=500,
        description="Short biography of the user.",
        example="Music enthusiast",
    )


class PrivateUserProfile(PublicUserProfile):
    email: EmailStr = Field(..., example="alex@example.com")


class UserProfileUpdate(BaseModel):
    avatarUrl: HttpUrl | None = Field(
        default=None,
        description="URL of the user's avatar image. Set to null to clear it.",
        example="https://example.com/avatar.jpg",
    )
    bio: str | None = Field(
        default=None,
        max_length=500,
        description="Short biography. Set to null to clear it.",
        example="Music enthusiast",
    )

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "UserProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be provided")
        return self
