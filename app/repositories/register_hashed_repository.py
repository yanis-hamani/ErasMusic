from app.models.auth import RegisterHashed

class RegisterHashedRepository:

    async def save(self, psql_conn, register: RegisterHashed) -> RegisterHashed:
        await psql_conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash)
            VALUES ($1, $2, $3, $4)
            """,
            register.id, register.username, register.email, register.hashed_password
        )
        return register

    async def select_by_email(self, psql_conn, email: str) -> RegisterHashed | None:
        record = await psql_conn.fetchrow(
            "SELECT id, username, email, password_hash FROM users WHERE email = $1",
            email
        )
        if not record:
            return None

        registerHashed = RegisterHashed(
            id = record["id"],
            username = record["username"],
            email= record["email"],
            hashed_password = record["password_hash"]
        )
        return registerHashed
        
