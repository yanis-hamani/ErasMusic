Use bolt protocol in neo4j browser

# ErasMusic

REST API built with **FastAPI** and **Neo4j**, running with Docker Compose.

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/)
- Git

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Configure environment variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Set your Neo4j password in `.env`:

```env
NEO4J_PASSWORD=your_password
```

Each developer has their own local configuration and database.

### 3. Start the application

Make sure Docker is running, then execute:

```bash
docker compose up -d --build
```

This will automatically start Neo4j and the FastAPI server.

### 4. Access the application

| Service | URL |
|---|---|
| Swagger UI (API documentation) | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |

**Neo4j credentials:**
- Username: `neo4j`
- Password: The password defined in your `.env` file.

## Useful Commands

**Start the application:**
```bash
docker compose up -d
```

**Rebuild after code changes:**
```bash
docker compose up -d --build
```

**Stop the application:**
```bash
docker compose down
```

**View logs:**
```bash
docker compose logs -f
```

## Notes

- Each developer runs their own local Neo4j database.
- Database data persists when containers are stopped or recreated.
- The `.env` file must not be committed to Git.
- Changing the password in `.env` does not reset the password of an existing Neo4j database.
