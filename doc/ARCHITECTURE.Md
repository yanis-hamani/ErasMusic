
Here is a scalable modular architecture designed around **FastAPI APIRouters** and **Clean Architecture** principles (separating endpoints, schemas, database access, and core logic).

### Recommended Directory Structure

```text
erasmusic-api/
├── app/
│   ├── __init__.py
│   ├── main.py                  # App initialization, lifespan, CORS, router inclusion
│   ├── config.py                # Environment variables & settings Management (pydantic-settings)
│   ├── dependencies.py          # Fastapi dependencies (get_db, get_neo4j, get_current_user)
│   │
│   ├── core/                    # Core application logic & utilities
│   │   ├── __init__.py
│   │   ├── database.py          # Connection management (asyncpg pool & Neo4j driver)
│   │   ├── security.py          # Password hashing, JWT token generation/validation
│   │   └── exceptions.py        # Custom exception handlers
│   │
│   ├── schemas/                 # Pydantic models for validation and serialization
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── friend.py
│   │   ├── group.py
│   │   ├── music.py             # Songs, Artists, Genres
│   │   ├── recommendation.py
│   │   ├── search.py
│   │   └── chat.py
│   │
│   ├── db/                      # Query layer (separates database calls from endpoints)
│   │   ├── __init__.py
│   │   ├── postgres/            # Asyncpg raw SQL or query helpers
│   │   │   ├── users.py
│   │   │   ├── chats.py
│   │   │   └── messages.py
│   │   └── neo4j/               # Cypher query functions
│   │       ├── social.py        # Friendships & requests
│   │       ├── groups.py
│   │       ├── music.py
│   │       └── recommendations.py
│   │
│   └── api/                     # API Routers organized by domain
│       ├── __init__.py
│       ├── v1/
│       │   ├── __init__.py
│       │   ├── router.py        # Combines all domain routers below
│       │   ├── auth.py          # /auth/*
│       │   ├── users.py         # /users/*
│       │   ├── friends.py       # /friends/* & /friend-requests/*
│       │   ├── groups.py        # /groups/*
│       │   ├── music.py         # /artists/*, /songs/*, /genres/*
│       │   ├── recommendations.py # /recommendations/*
│       │   ├── search.py        # /search/*
│       │   └── chats.py         # /chats/*
│       └── health.py            # Healthcheck endpoint
│
├── .env.example
├── docker-compose.yml
└── requirements.txt

```

---

### Router Organization Breakdown

1. **`api/v1/auth.py`**
* `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`
* *DB usage:* Writes/reads user credentials in **PostgreSQL**; creates corresponding `:User` node in **Neo4j**.


2. **`api/v1/users.py`**
* `/users/me` (GET, PATCH, DELETE), `/users/{userId}` (GET)
* *DB usage:* Core profile data in **PostgreSQL**; Syncs updates/deletions to **Neo4j** `:User` node.


3. **`api/v1/friends.py`**
* `/friends`, `/friends/{userId}`, `/friend-requests`, `/friend-requests/{requestId}/accept|decline`
* *DB usage:* Managed entirely in **Neo4j** via `:FRIENDS_WITH` and `:REQUESTED_FRIENDSHIP` relationships.


4. **`api/v1/groups.py`**
* `/groups`, `/groups/{groupId}`, `/groups/{groupId}/members`, `/groups/{groupId}/tags`
* *DB usage:* **Neo4j** for group metadata, member relationships (`:PARTS_OF`), and tags (`:TAGGED_WITH`); **PostgreSQL** if linked to a group chat (`psqlChatId`).


5. **`api/v1/music.py`**
* `/artists`, `/songs`, `/genres`
* *DB usage:* Managed in **Neo4j** (`:Song`, `:Artists`, `:Genre` nodes and relationships like `:PERFORMED_BY`, `:RELATED_TO`).


6. **`api/v1/recommendations.py`**
* `/recommendations/friends/*`, `/recommendations/groups/*`
* *DB usage:* Graph traversal queries in **Neo4j** analyzing shared taste (`:LISTEN_TO`, `:STREAMS`, `:LIKES`) and mutual connections.


7. **`api/v1/search.py`**
* `/search/users`, `/search/groups`
* *DB usage:* Full-text search or text-matching queries across **PostgreSQL** (users) and **Neo4j** (groups/taste tags).


8. **`api/v1/chats.py`**
* `/chats`, `/chats/{chatId}`, `/chats/{chatId}/messages`, `/chats/{chatId}/members`
* *DB usage:* Managed in **PostgreSQL** (`chats`, `chat_participants`, `chat_messages` tables).



---

### How to tie routers together in `main.py`

#### `app/api/v1/router.py`

```python
from fastapi import APIRouter
from app.api.v1 import auth, users, friends, groups, music, recommendations, search, chats

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(friends.router, tags=["Friends"])
api_router.include_router(groups.router, prefix="/groups", tags=["Groups"])
api_router.include_router(music.router, tags=["Music"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(chats.router, prefix="/chats", tags=["Chats"])

```

#### `app/main.py`

```python
from fastapi import FastAPI
from app.core.database import lifespan
from app.api.v1.router import api_router
from app.api.health import router as health_router

app = FastAPI(
    title="ErasMusic API",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health_router)
app.include_router(api_router)

```

Whenever you are ready, share the specific endpoint or domain swagger section you'd like to work on first!
