import os
import asyncpg
from contextlib import asynccontextmanager
from fastapi import FastAPI
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
DATABASE_URL = os.environ["DATABASE_URL"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Neo4j Driver
    neo4j_driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    
    # Initialize Postgres Connection Pool
    pg_pool = await asyncpg.create_pool(DATABASE_URL)

    try:
        neo4j_driver.verify_connectivity()
        app.state.neo4j_driver = neo4j_driver
        app.state.pg_pool = pg_pool
        yield
    finally:
        neo4j_driver.close()
        await pg_pool.close()
