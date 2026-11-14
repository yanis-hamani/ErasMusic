# ErasMusic architecture

ErasMusic is an asynchronous FastAPI application backed by PostgreSQL and
Neo4j. PostgreSQL stores transactional application data; Neo4j stores the
social and music graph used for discovery and recommendations.

## System overview

```mermaid
flowchart LR
    Client[API client] -->|HTTP :8000| API[FastAPI / Uvicorn]
    API -->|asyncpg| PostgreSQL[(PostgreSQL)]
    API -->|Neo4j driver| Neo4j[(Neo4j)]
    API -->|OAuth and Web API| Spotify[Spotify]
    PostgreSQL --> PGVolume[(postgres_data)]
    Neo4j --> NeoVolume[(neo4j_data)]
```

| Component | Responsibility |
|---|---|
| FastAPI | HTTP routing, validation, authentication and OpenAPI documentation |
| PostgreSQL | Users, refresh tokens, chats, messages, OAuth state and encrypted Spotify credentials |
| Neo4j | Friendships, groups, imported music catalog, affinities and recommendations |
| Spotify | Optional OAuth identity, top tracks/artists and live catalog search |
| Dishka | Creates application-scoped database connections and request-scoped services/repositories |
| Docker Compose | Runs the API and databases, applies schemas and optionally loads sample data |

## Docker architecture

The Compose stack contains these services:

| Service | Lifecycle |
|---|---|
| `postgres` | Persistent PostgreSQL 16 instance; applies `scripts/psql-init/` when its volume is first created |
| `neo4j` | Persistent Neo4j instance with HTTP and Bolt interfaces |
| `neo4j-init` | One-shot service that waits for Neo4j and applies uniqueness constraints |
| `api` | Builds the Python image and starts Uvicorn after PostgreSQL is healthy and Neo4j initialization succeeds |
| `postgres-seed`, `neo4j-seed` | Optional one-shot services enabled by the `seed` profile |

Database files are stored in named volumes. The API source and tests are bind
mounted for development, and Uvicorn runs with automatic reload. Database and
secret values are provided through environment variables.

## API layers

```mermaid
flowchart LR
    Request[HTTP request] --> Router
    Router --> Service
    Service --> Repository
    Repository --> Database[(PostgreSQL or Neo4j)]
    Models[Pydantic models] -. validation and response types .-> Router
    Models -. domain data .-> Service
    Dishka[Dishka container] -. injects .-> Router
```

| Layer | Location | Responsibility |
|---|---|---|
| Model | `app/models/` | Pydantic request, response and internal data structures |
| Repository | `app/repositories/` | SQL and Cypher queries, with database results converted into models |
| Service | `app/services/` | Business rules, authorization decisions, pagination and transaction orchestration |
| Router | `app/routers/` | Paths, HTTP methods, query parameters, authentication dependencies and status codes |

Routers do not query databases directly. Dishka injects request-scoped services
and repositories. The PostgreSQL pool and Neo4j driver are application-scoped
and are opened and closed with the FastAPI application.

Some operations span both databases. Registration creates a PostgreSQL user and
its Neo4j `User`; group operations synchronize a Neo4j membership with the
linked PostgreSQL chat; qualifying chat activity updates Neo4j closeness. These
workflows keep the PostgreSQL transaction open until the Neo4j operation
succeeds. There is no distributed transaction coordinator, so PostgreSQL and
Neo4j remain separate consistency boundaries.

Spotify synchronization is another cross-store workflow. PostgreSQL claims a
sync and stores its final status, while one Neo4j write transaction replaces
all three periods of music affinity. A graph failure leaves the previous graph
state intact and records the failed attempt in PostgreSQL. Spotify catalog
search is read-through only and does not write either database.

## PostgreSQL schema

```mermaid
erDiagram
    USERS ||--o{ REFRESH_TOKENS : owns
    USERS ||--o| SPOTIFY_CONNECTIONS : links
    USERS ||--o{ SPOTIFY_OAUTH_STATES : authorizes
    USERS ||--o{ CHAT_PARTICIPANTS : joins
    CHATS ||--o{ CHAT_PARTICIPANTS : contains
    USERS ||--o{ CHAT_MESSAGES : sends
    CHATS ||--o{ CHAT_MESSAGES : contains

    USERS {
        varchar id PK
        varchar username UK
        varchar email UK
        varchar password_hash
        text avatar_url
        text bio
    }
    REFRESH_TOKENS {
        varchar token_hash PK
        varchar user_id FK
        timestamptz created_at
    }
    SPOTIFY_CONNECTIONS {
        varchar user_id PK,FK
        varchar spotify_user_id UK
        text access_token_encrypted
        text refresh_token_encrypted
        timestamptz access_token_expires_at
        text scopes
        timestamptz connected_at
        timestamptz last_successful_sync_at
        timestamptz sync_started_at
        text last_sync_error
        boolean reconnect_required
    }
    SPOTIFY_OAUTH_STATES {
        varchar state_hash PK
        varchar user_id FK
        timestamptz expires_at
        timestamptz created_at
    }
    CHATS {
        varchar id PK
        enum type
        timestamptz created_at
        date last_closeness_activity_date
    }
    CHAT_PARTICIPANTS {
        varchar chat_id PK,FK
        varchar user_id PK,FK
    }
    CHAT_MESSAGES {
        varchar id PK
        varchar chat_id FK
        varchar sender_id FK
        text message
        timestamptz created_at
    }
```

- `chats.type` is either `direct` or `group`.
- `last_closeness_activity_date` prevents more than one closeness increase per
  direct chat and UTC day.
- Triggers enforce at most two direct-chat participants, require message
  senders to be participants, and remove invalid chats after membership removal.
- Foreign keys cascade chat, participant and token cleanup where appropriate.
- Spotify access and refresh tokens are encrypted with a dedicated Fernet key.
  OAuth state is stored only as a SHA-256 hash, expires after ten minutes and is
  deleted on first use.
- `sync_started_at` is a short-lived synchronization claim. Only
  `last_successful_sync_at` satisfies the once-per-UTC-day login guard; failures
  remain eligible for a later login attempt.

## Neo4j schema

```mermaid
flowchart LR
    U1[User] -->|REQUESTED_FRIENDSHIP| U2[User]
    U1 ---|FRIENDS_WITH| U2
    U1 -->|LISTEN_TO| Song
    U1 -->|TOP_ARTIST| Artist[Artists]
    Song -->|PERFORMED_BY| Artist[Artists]
    Song -->|RELATED_TO| Genre
    Artist -->|RELATED_TO| Genre
    U1 -->|PARTS_OF| Group
    Group -->|TAGGED_WITH| Artist
    Group -->|TAGGED_WITH| Genre
```

| Element | Important properties |
|---|---|
| `User` | `psqlId`, `username` |
| `Group` | `id`, `psqlChatId`, `ownerId`, `name`, `description` |
| `Song` | `id`, `title`, `coverURL`, `spotifyURL` |
| `Artists` | `id`, `name`, `profilePicture`, `spotifyURL` |
| `Genre` | `id`, `name`, `normalizedName` |
| `FRIENDS_WITH` | `closeness`, `closenessUpdatedAt` |
| `REQUESTED_FRIENDSHIP` | `requestId`, `pairKey`, `status`, `createdAt` |
| `LISTEN_TO` | `shortTermScore`, `mediumTermScore`, `longTermScore` |
| `TOP_ARTIST` | `shortTermScore`, `mediumTermScore`, `longTermScore` |
| `PARTS_OF` | `role`, `joinedAt` |

`User.psqlId` references the logical PostgreSQL user, while
`Group.psqlChatId` identifies the group's PostgreSQL chat. Neo4j constraints
make these identifiers, entity IDs and friendship-request identifiers unique.
Spotify song and artist IDs are used as graph IDs. Genre IDs are stable hashes
of normalized names, and `Genre.normalizedName` is unique so differently cased
copies converge on the same node. Imported ranks 1 through 50 become scores 50
through 1. Each period is replaced in full, then affinity relationships with no
remaining positive period are removed.

Disconnecting Spotify removes the user's `LISTEN_TO` and `TOP_ARTIST`
relationships. Shared `Song`, `Artists`, and `Genre` nodes remain in the catalog
for other users and seeded data.
