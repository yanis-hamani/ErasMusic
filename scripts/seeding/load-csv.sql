\copy users FROM '/scripts/psql_users.csv' WITH CSV HEADER;
\copy chats (id, type) FROM '/scripts/psql_chats.csv' WITH CSV HEADER;
\copy chat_participants FROM '/scripts/psql_chat_participants.csv' WITH CSV HEADER;
\copy chat_messages FROM '/scripts/psql_chat_messages.csv' WITH CSV HEADER;
\copy refresh_tokens FROM '/scripts/psql_refresh_tokens.csv' WITH CSV HEADER;
