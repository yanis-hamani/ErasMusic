class ChatPsqlRepository:
    @staticmethod
    async def create_group_chat(psql_conn, chat_id: str, owner_id: str) -> None:
        await psql_conn.execute(
            "INSERT INTO chats (id, type) VALUES ($1, 'group')",
            chat_id,
        )
        await psql_conn.execute(
            "INSERT INTO chat_participants (chat_id, user_id) VALUES ($1, $2)",
            chat_id,
            owner_id,
        )

    @staticmethod
    async def delete_chat(psql_conn, chat_id: str) -> bool:
        deleted_id = await psql_conn.fetchval(
            "DELETE FROM chats WHERE id = $1 RETURNING id",
            chat_id,
        )
        return deleted_id is not None

    @staticmethod
    async def add_participant(psql_conn, chat_id: str, user_id: str) -> None:
        await psql_conn.execute(
            "INSERT INTO chat_participants (chat_id, user_id) VALUES ($1, $2)",
            chat_id,
            user_id,
        )

    @staticmethod
    async def remove_participant(psql_conn, chat_id: str, user_id: str) -> bool:
        deleted = await psql_conn.fetchval(
            """
            DELETE FROM chat_participants
            WHERE chat_id = $1 AND user_id = $2
            RETURNING user_id
            """,
            chat_id,
            user_id,
        )
        return deleted is not None
