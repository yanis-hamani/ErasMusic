# ErasMusic

ErasMusic is a social media platform that lets you meet new people through shared musical tastes.

## Documentation

- [Architecture](doc/architecture.md)
- [Functional behavior](doc/functional.md)

## Quick start

1. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

   The example values are suitable for local development. Change them if the
   project will run outside your machine. Spotify variables may remain empty
   when the optional integration is not needed.

2. Choose one startup mode.

   **Start with empty databases:**

   ```bash
   docker compose up -d --build
   ```

   **Start with sample data** (recommended when exploring the API):

   ```bash
   docker compose --profile seed up -d --build
   docker compose logs -f postgres-seed neo4j-seed
   ```

   Wait for both seed services to report that seeding is complete.

   The sample dataset contains a stable account with listening activity,
   friendships, chats, and recommendation data:

   - Username: `demo`
   - Email: `demo@example.com`
   - Password: `StrongPassword123`

3. Verify the API and both databases:

   ```bash
   curl http://localhost:8000/health
   ```

   A successful response reports both PostgreSQL and Neo4j as connected.

## Optional Spotify setup

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Add this redirect URI to the app settings exactly as written:

   ```text
   http://localhost:8000/spotify/callback
   ```

3. Generate a dedicated Fernet key. Do not reuse `SECRET_KEY`:

   ```bash
   python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

4. Set the following values in your local `.env`:

   ```dotenv
   SPOTIFY_CLIENT_ID=your-dashboard-client-id
   SPOTIFY_CLIENT_SECRET=your-dashboard-client-secret
   SPOTIFY_REDIRECT_URI=http://localhost:8000/spotify/callback
   SPOTIFY_TOKEN_ENCRYPTION_KEY=the-generated-fernet-key
   ```

The redirect URI must match the Dashboard value exactly, including scheme,
host, port and path. In Spotify Development Mode, the app owner currently needs
Spotify Premium and the app can have at most five allowlisted users. Add every
tester in the Dashboard before they try to connect.

After logging in to ErasMusic, call `GET /spotify/connect` with the access token
and open the returned `authorizationUrl`. Spotify redirects to the callback,
which stores encrypted credentials and attempts the initial import. Connection
status and any synchronization error are available from `GET /spotify/status`.
See `/docs` for all Spotify routes.

## Service URLs

| Service | Address |
|---|---|
| Swagger UI | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |
| Health check | <http://localhost:8000/health> |
| Neo4j Browser | <http://localhost:7474> |
| PostgreSQL | `localhost:5432` |
| Neo4j Bolt | `bolt://localhost:7687` |

Neo4j Browser credentials:

- Username: `neo4j`
- Password: the `NEO4J_PASSWORD` value in `.env`
- Connection URL: `bolt://localhost:7687`

PostgreSQL development connection:

- Username: the `POSTGRES_USER` value in `.env` (default: `myuser`)
- Database: the `POSTGRES_DB` value in `.env` (default: `mydatabase`)
- Password: the `POSTGRES_PASSWORD` value in `.env`

## Development workflow

The `app/` and `tests/` directories are mounted into the API container, and
Uvicorn runs with reload enabled. Python source and test changes are available
without rebuilding the image.

Rebuild only after changing `Dockerfile` or `requirements.txt`:

```bash
docker compose up --build
```

## Running tests

When the API container is running:

```bash
docker compose exec api python -m unittest discover -v
```

Without an existing API container:

```bash
docker compose run --rm api python -m unittest discover -v
```

### Reset and reseed

The following command permanently deletes all local PostgreSQL and Neo4j data:

```bash
docker compose down -v --remove-orphans
```

Then recreate and seed everything:

```bash
docker compose --profile seed up -d --build
docker compose logs -f postgres-seed neo4j-seed
```

Use the same reset procedure after changing PostgreSQL initialization scripts
or when a seed import fails partway through. Existing installations created
before the Spotify tables were added must be reset (or migrated manually),
because `scripts/psql-init/` runs only when the PostgreSQL volume is first
created.

## Troubleshooting

### A password change is ignored

Database credentials are initialized when volumes are created. Changing `.env`
does not update credentials in existing volumes. Reset the volumes and start the
stack again.
