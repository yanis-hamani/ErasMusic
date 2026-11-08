from app.models.auth import RefreshToken

class RefreshTokenRepository:

    async def save(self, psql_conn, refresh_token: RefreshToken) -> RefreshToken:
        await psql_conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash)
            VALUES ($1, $2)
            """,
            refresh_token.user_id, refresh_token.hashed_token
        )
        return refresh_token

    async def delete(self, psql_conn, refresh_token: RefreshToken) -> None:
        await psql_conn.execute(
            "DELETE FROM refresh_tokens WHERE user_id = $1 AND token_hash = $2",
            refresh_token.user_id, refresh_token.hashed_token
        )

    async def exists(self, psql_conn, refresh_token: RefreshToken) -> bool:
        exists = await psql_conn.fetchval(
            "SELECT 1 FROM refresh_tokens WHERE user_id = $1 AND token_hash = $2",
            refresh_token.user_id, refresh_token.hashed_token
        )
        return exists
        
