from app.models.common import HTTPError, HTTPValidationError


API_DESCRIPTION = (
    "ErasMusic is a social network for meeting people who share similar music "
    "tastes. The API uses PostgreSQL for relational data and Neo4j for social "
    "and music graph data."
)

TAGS_METADATA = [
    {"name": "System", "description": "Application and dependency health checks"},
    {
        "name": "Authentication",
        "description": "PostgreSQL — User registration, login, token refresh, and logout",
    },
    {"name": "User Profiles", "description": "PostgreSQL — User profile data"},
    {
        "name": "Friends & Social",
        "description": (
            "Neo4j — Social graph connections, friends, and friend request lifecycles"
        ),
    },
    {
        "name": "Groups",
        "description": "Neo4j — Group management, memberships, and metadata tags",
    },
    {
        "name": "Music Data",
        "description": "Neo4j — Music catalog browsing (artists, songs, genres)",
    },
    {
        "name": "Recommendations",
        "description": (
            "Neo4j — Time-based graph traversal discovery and personalized "
            "recommendations"
        ),
    },
    {
        "name": "Search",
        "description": "PostgreSQL and Neo4j — User and group search",
    },
    {
        "name": "Chat",
        "description": (
            "PostgreSQL — Conversations, message history, and participation "
            "management. Mutual daily activity in direct chats updates "
            "time-decayed friendship closeness in Neo4j."
        ),
    },
]

UNAUTHORIZED_RESPONSE = {
    "model": HTTPError,
    "description": "Missing or invalid authentication token",
}
FORBIDDEN_RESPONSE = {
    "model": HTTPError,
    "description": "The authenticated user is not allowed to perform this action",
}
NOT_FOUND_RESPONSE = {
    "model": HTTPError,
    "description": "The requested resource was not found",
}
CONFLICT_RESPONSE = {
    "model": HTTPError,
    "description": "Duplicate key or entity conflict",
}
VALIDATION_RESPONSE = {
    "model": HTTPValidationError,
    "description": "Request validation failed",
}

REFRESH_COOKIE_HEADER = {
    "description": (
        "Sets the refresh_token session cookie with HttpOnly, Secure, and "
        "SameSite=Lax attributes."
    ),
    "schema": {
        "type": "string",
        "example": (
            "refresh_token=eyJhbGciOiJIUzI1NiJ9...; Path=/; HttpOnly; Secure; "
            "SameSite=Lax"
        ),
    },
}

CLEARED_REFRESH_COOKIE_HEADER = {
    "description": "Clears the refresh_token cookie.",
    "schema": {
        "type": "string",
        "example": (
            'refresh_token=""; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax'
        ),
    },
}

REFRESH_COOKIE_DESCRIPTION = "HTTP-only refresh-token cookie set by register or login"
PAGE_DESCRIPTION = "Page number to retrieve, starting at 1"
LIMIT_DESCRIPTION = "Maximum number of items to return"
PERIOD_DESCRIPTION = "Time window used to calculate recommendations"
SEARCH_DESCRIPTION = (
    "Non-blank search term. Leading and trailing whitespace is ignored, and "
    "wildcard characters such as % and _ are matched literally."
)
