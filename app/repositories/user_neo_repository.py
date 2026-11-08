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

    async def delete_by_psql_id(self, neo4j_transaction, psql_id: str) -> bool:
        result = await neo4j_transaction.run(
            "MATCH (u:User {psqlId: $psql_id}) DETACH DELETE u",
            psql_id=psql_id,
        )
        summary = await result.consume()
        return summary.counters.nodes_deleted > 0
        
