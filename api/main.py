import os
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from neo4j import GraphDatabase

# AI Generated, we'll do API afterwards, now we can test the database connection.

# 1. Config

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
NEO4J_DATABASE = os.environ["NEO4J_DATABASE"]


# 2. Auth Neo4j

@asynccontextmanager
async def lifespan(app: FastAPI):

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    try:
        driver.verify_connectivity()
        app.state.driver = driver

        yield

    finally:
        driver.close()


# 3. FastAPI app creation

app = FastAPI(
    title="ErasMusic API",
    description="Neo4j API for ErasMusic",
    version="1.0.0",
    lifespan=lifespan
)

#Tests

# 4. Data model (TO DO)

class User(BaseModel):
    name: str = Field(min_length=1)


# 5. Endpoints (TO DO)

@app.get("/health")
def health(request: Request):

    request.app.state.driver.verify_connectivity()

    return {
        "status": "ok",
        "database": "Neo4j"
    }


@app.get("/users")
def get_users(request: Request):

    query = """
    MATCH (p:User)
    RETURN p.id AS id, p.name AS name
    ORDER BY name
    """

    records, _, _ = request.app.state.driver.execute_query(
        query,
        database_=NEO4J_DATABASE
    )

    return [record.data() for record in records]


@app.post("/users", status_code=201)
def create_user(
    user: User,
    request: Request
):

    query = """
    CREATE (p:User {
        id: $id,
        name: $name
    })

    RETURN p.id AS id, p.name AS name
    """

    records, _, _ = request.app.state.driver.execute_query(
        query,
        id=str(uuid4()),
        name=user.name,
        database_=NEO4J_DATABASE
    )

    return records[0].data()