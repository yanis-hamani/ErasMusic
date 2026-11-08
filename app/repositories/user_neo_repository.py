import asyncpg
from app.models.auth import UserNeo

class UserNeoRepository:

    async def save(self, neo4j_session, user: UserNeo) -> UserNeo:
        result = await neo4j_session.run(
            "CREATE (u:User {username: $username, psqlId: $psql_id})",
            psql_id=user.psql_id,
            username=user.username
        )
        await result.consume()
        return user
        
