-- seed.sql

-- 1. Begin a transaction to ensure all or nothing is inserted
BEGIN;

-- (Optional) Clear existing data for idempotency (run this script multiple times safely)
-- CASCADE will automatically clean up child tables like participants and messages
TRUNCATE TABLE users, chats CASCADE;

-- 2. Seed Users
-- Ensuring usernames are >= 3 chars as per check_username_length
INSERT INTO users (id, username, email, password_hash, avatar_url, bio) VALUES
('usr_1', 'alice', 'alice@example.com', 'hashed_pw_1', 'https://avatar.com/alice.jpg', 'Loves direct messages.'),
('usr_2', 'bob_builder', 'bob@example.com', 'hashed_pw_2', NULL, 'Group chat enthusiast.'),
('usr_3', 'charlie', 'charlie@example.com', 'hashed_pw_3', 'https://avatar.com/charlie.jpg', 'Just here to chat.');

-- 3. Seed Chats
-- Creating one direct chat and one group chat
INSERT INTO chats (id, type) VALUES
('chat_1', 'direct'),
('chat_2', 'group');

-- 4. Seed Chat Participants
-- Must be inserted BEFORE messages due to check_sender_is_participant trigger
-- Also respecting the check_direct_chat_limit trigger (max 2 for 'direct')
INSERT INTO chat_participants (chat_id, user_id) VALUES
-- Direct chat between Alice and Bob
('chat_1', 'usr_1'),
('chat_1', 'usr_2'),

-- Group chat with Alice, Bob, and Charlie
('chat_2', 'usr_1'),
('chat_2', 'usr_2'),
('chat_2', 'usr_3');

-- 5. Seed Chat Messages
-- Ensuring messages are not empty as per check_message_not_empty
-- Senders are strictly participants of the respective chats
INSERT INTO chat_messages (id, chat_id, sender_id, message, created_at) VALUES
-- Messages in direct chat
('msg_1', 'chat_1', 'usr_1', 'Hey Bob, did you see the new DB schema?', CURRENT_TIMESTAMP - INTERVAL '2 hours'),
('msg_2', 'chat_1', 'usr_2', 'Yes! The triggers look solid.', CURRENT_TIMESTAMP - INTERVAL '1 hour'),

-- Messages in group chat
('msg_3', 'chat_2', 'usr_3', 'Hey everyone, welcome to the group!', CURRENT_TIMESTAMP - INTERVAL '30 minutes'),
('msg_4', 'chat_2', 'usr_1', 'Thanks Charlie!', CURRENT_TIMESTAMP - INTERVAL '25 minutes'),
('msg_5', 'chat_2', 'usr_2', 'Glad to be here.', CURRENT_TIMESTAMP - INTERVAL '20 minutes');

-- Commit the transaction
COMMIT;
