# app/database.py
import os
import asyncpg
from typing import AsyncGenerator
from neo4j import AsyncGraphDatabase, AsyncDriver
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
DATABASE_URL = os.environ["DATABASE_URL"]

async def init_neo4j_driver() -> AsyncGenerator[AsyncDriver, None]:
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    await driver.verify_connectivity()
    yield driver
    await driver.close()

async def init_pg_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    pool = await asyncpg.create_pool(DATABASE_URL)
    yield pool
    await pool.close()
