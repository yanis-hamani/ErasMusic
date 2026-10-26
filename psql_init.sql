CREATE TYPE chat_type_enum AS ENUM ('direct', 'group');

CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    bio TEXT
);

CREATE TABLE chats (
    id VARCHAR(50) PRIMARY KEY,
    type chat_type_enum NOT NULL DEFAULT 'direct'
);

-- TODO: Constraint to prevent user chat to have more other than two participant
CREATE TABLE chat_participants (
    chat_id VARCHAR(50) NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (chat_id, user_id)
);

-- TODO: Constraint to prevent a message to besend in a chat your not in
CREATE TABLE chat_messages (
    id VARCHAR(50) PRIMARY KEY,
    chat_id VARCHAR(50) NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    sender_id VARCHAR(50) REFERENCES users(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Fast lookups for authentication
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);

-- Fast lookups for chat queries
CREATE INDEX idx_chat_participants_user_id ON chat_participants(user_id);
CREATE INDEX idx_chat_messages_chat_id_created_at ON chat_messages(chat_id, created_at DESC);

-- Some constraint on top of my head, we may implement more to ensure data quality
CREATE OR REPLACE FUNCTION check_direct_chat_limit()
RETURNS TRIGGER AS $$
DECLARE
    participant_count INT;
    c_type chat_type_enum;
BEGIN
    SELECT type INTO c_type FROM chats WHERE id = NEW.chat_id;
    
    IF c_type = 'direct' THEN
        SELECT COUNT(*) INTO participant_count 
        FROM chat_participants 
        WHERE chat_id = NEW.chat_id;
        
        IF participant_count >= 2 THEN
            RAISE EXCEPTION 'A direct chat cannot have more than two participants.';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION check_sender_is_participant()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM chat_participants 
        WHERE chat_id = NEW.chat_id AND user_id = NEW.sender_id
    ) THEN
        RAISE EXCEPTION 'Sender must be a participant of the chat to send a message.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_sender_is_participant
BEFORE INSERT ON chat_messages
FOR EACH ROW
EXECUTE FUNCTION check_sender_is_participant();

CREATE TRIGGER enforce_direct_chat_limit
BEFORE INSERT ON chat_participants
FOR EACH ROW
EXECUTE FUNCTION check_direct_chat_limit();

ALTER TABLE chat_messages 
ADD CONSTRAINT check_message_not_empty 
CHECK (TRIM(message) <> '');

ALTER TABLE users 
ADD CONSTRAINT check_username_length 
CHECK (length(TRIM(username)) >= 3);
