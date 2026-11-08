import asyncpg
from app.models.auth import UserPsql

class UserPsqlRepository:

 async def select_by_id(self, psql_conn, id: str) -> UserPsql | None:
    record = await psql_conn.fetchrow(
        "SELECT id, username, email, avatar_url, bio FROM users WHERE id = $1",
        id
    )
    if not record:
        return None

    user = UserPsql(
        id = record["id"],
        username = record["username"],
        email= record["email"],
        avatar_url= record["avatar_url"],
        bio = record["bio"],
    )
    return user
