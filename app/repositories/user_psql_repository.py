from typing import Any

from app.models.users import UserRecord

class UserPsqlRepository:

    @staticmethod
    def _to_user(record) -> UserRecord | None:
        if not record:
            return None

        return UserRecord(
            id=record["id"],
            username=record["username"],
            email=record["email"],
            avatar_url=record["avatar_url"],
            bio=record["bio"],
        )

    async def select_by_id(self, psql_conn, user_id: str) -> UserRecord | None:
        record = await psql_conn.fetchrow(
            "SELECT id, username, email, avatar_url, bio FROM users WHERE id = $1",
            user_id,
        )
        return self._to_user(record)

    async def update_profile(
        self,
        psql_conn,
        user_id: str,
        updates: dict[str, Any],
    ) -> UserRecord | None:
        column_names = {
            "avatar_url": "avatar_url",
            "bio": "bio",
        }
        invalid_fields = updates.keys() - column_names.keys()
        if invalid_fields:
            raise ValueError(f"Unsupported profile fields: {sorted(invalid_fields)}")

        assignments = []
        values: list[Any] = [user_id]
        for field, value in updates.items():
            values.append(value)
            assignments.append(f"{column_names[field]} = ${len(values)}")

        record = await psql_conn.fetchrow(
            f"""
            UPDATE users
            SET {', '.join(assignments)}
            WHERE id = $1
            RETURNING id, username, email, avatar_url, bio
            """,
            *values,
        )
        return self._to_user(record)

    async def delete(self, psql_conn, user_id: str) -> bool:
        deleted_id = await psql_conn.fetchval(
            "DELETE FROM users WHERE id = $1 RETURNING id",
            user_id,
        )
        return deleted_id is not None
