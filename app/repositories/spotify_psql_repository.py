from datetime import date, datetime, timedelta

from app.models.spotify import SpotifyConnectionRecord


class SpotifyPsqlRepository:
    @staticmethod
    async def create_oauth_state(
        connection,
        state_hash: str,
        user_id: str,
        expires_at: datetime,
    ) -> None:
        await connection.execute(
            """
            DELETE FROM spotify_oauth_states
            WHERE user_id = $1 OR expires_at <= CURRENT_TIMESTAMP
            """,
            user_id,
        )
        await connection.execute(
            """
            INSERT INTO spotify_oauth_states (state_hash, user_id, expires_at)
            VALUES ($1, $2, $3)
            """,
            state_hash,
            user_id,
            expires_at,
        )

    @staticmethod
    async def consume_oauth_state(connection, state_hash: str) -> str | None:
        return await connection.fetchval(
            """
            DELETE FROM spotify_oauth_states
            WHERE state_hash = $1 AND expires_at > CURRENT_TIMESTAMP
            RETURNING user_id
            """,
            state_hash,
        )

    @staticmethod
    async def upsert_connection(
        connection,
        record: SpotifyConnectionRecord,
    ) -> SpotifyConnectionRecord:
        row = await connection.fetchrow(
            """
            INSERT INTO spotify_connections (
                user_id,
                spotify_user_id,
                access_token_encrypted,
                refresh_token_encrypted,
                access_token_expires_at,
                scopes,
                connected_at,
                reconnect_required,
                last_sync_error
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, NULL)
            ON CONFLICT (user_id) DO UPDATE SET
                spotify_user_id = EXCLUDED.spotify_user_id,
                access_token_encrypted = EXCLUDED.access_token_encrypted,
                refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                access_token_expires_at = EXCLUDED.access_token_expires_at,
                scopes = EXCLUDED.scopes,
                connected_at = EXCLUDED.connected_at,
                reconnect_required = FALSE,
                last_sync_error = NULL
            RETURNING *
            """,
            record.user_id,
            record.spotify_user_id,
            record.access_token_encrypted,
            record.refresh_token_encrypted,
            record.access_token_expires_at,
            record.scopes,
            record.connected_at,
        )
        return SpotifyPsqlRepository._record(row)

    @staticmethod
    async def select_connection(
        connection,
        user_id: str,
    ) -> SpotifyConnectionRecord | None:
        row = await connection.fetchrow(
            "SELECT * FROM spotify_connections WHERE user_id = $1",
            user_id,
        )
        return SpotifyPsqlRepository._record(row)

    @staticmethod
    async def update_tokens(
        connection,
        user_id: str,
        access_token_encrypted: str,
        refresh_token_encrypted: str,
        expires_at: datetime,
        scopes: str,
    ) -> None:
        await connection.execute(
            """
            UPDATE spotify_connections
            SET access_token_encrypted = $2,
                refresh_token_encrypted = $3,
                access_token_expires_at = $4,
                scopes = CASE WHEN $5 = '' THEN scopes ELSE $5 END,
                reconnect_required = FALSE
            WHERE user_id = $1
            """,
            user_id,
            access_token_encrypted,
            refresh_token_encrypted,
            expires_at,
            scopes,
        )

    @staticmethod
    async def claim_sync(
        connection,
        user_id: str,
        now: datetime,
        utc_date: date,
        force: bool,
    ) -> SpotifyConnectionRecord | None:
        row = await connection.fetchrow(
            """
            UPDATE spotify_connections
            SET sync_started_at = $2,
                last_sync_error = NULL
            WHERE user_id = $1
              AND reconnect_required = FALSE
              AND (sync_started_at IS NULL OR sync_started_at < $2 - INTERVAL '15 minutes')
              AND (
                  $4
                  OR last_successful_sync_at IS NULL
                  OR (last_successful_sync_at AT TIME ZONE 'UTC')::date < $3
              )
            RETURNING *
            """,
            user_id,
            now,
            utc_date,
            force,
        )
        return SpotifyPsqlRepository._record(row)

    @staticmethod
    async def complete_sync(connection, user_id: str, synced_at: datetime) -> None:
        await connection.execute(
            """
            UPDATE spotify_connections
            SET last_successful_sync_at = $2,
                sync_started_at = NULL,
                last_sync_error = NULL
            WHERE user_id = $1
            """,
            user_id,
            synced_at,
        )

    @staticmethod
    async def fail_sync(
        connection,
        user_id: str,
        error: str,
        reconnect_required: bool = False,
    ) -> None:
        await connection.execute(
            """
            UPDATE spotify_connections
            SET sync_started_at = NULL,
                last_sync_error = $2,
                reconnect_required = reconnect_required OR $3
            WHERE user_id = $1
            """,
            user_id,
            error[:1000],
            reconnect_required,
        )

    @staticmethod
    async def delete_connection(connection, user_id: str) -> bool:
        status = await connection.execute(
            "DELETE FROM spotify_connections WHERE user_id = $1",
            user_id,
        )
        return status == "DELETE 1"

    @staticmethod
    def _record(row) -> SpotifyConnectionRecord | None:
        if row is None:
            return None
        return SpotifyConnectionRecord(**dict(row))
