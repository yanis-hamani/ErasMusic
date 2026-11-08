# TODO:  AJOUTER USERNAME a NEO4J

import csv
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

# ==========================================
# CONFIGURATION - Scale these as needed
# ==========================================
NUM_USERS = 1000
NUM_DIRECT_CHATS = 500
NUM_GROUP_CHATS = 50
MESSAGES_PER_CHAT_MAX = 20

NUM_SONGS = 500
NUM_ARTISTS = 100
GENRES = ['Synthwave', 'Retrowave', 'Cyberpunk', 'House', 'Techno', 'Rock', 'Jazz']

# ==========================================
# HELPER TO WRITE CSVs
# ==========================================
def write_csv(filename, data, fieldnames):
    print(f"Writing {filename}...")
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

# ==========================================
# 1. GENERATE BASE ENTITIES
# ==========================================
print("Generating Entities...")

# StrongPassword123
known_password_hashed = '$argon2id$v=19$m=65536,t=3,p=4$KaWUkrI2JqT03ptzDgHA2A$nx23EtGHpVMkwnIkxkU/UJZMcAZNmAzBf/bxA72b4cw'

# Users
users = []
for _ in range(NUM_USERS):
    users.append({
        'id': f"user_{uuid.uuid4().hex[:12]}",
        'username': fake.unique.user_name() + str(random.randint(10, 99)), # ensure length >= 3
        'email': fake.unique.email(),
        'password_hash': known_password_hashed,
        'avatar_url': fake.image_url(),
        'bio': fake.text(max_nb_chars=100)
    })
user_ids = [u['id'] for u in users]

# Refresh Tokens
tokens = [{
    'token_hash': fake.sha256(),
    'user_id': u['id'],
    'created_at': fake.date_time_this_year().isoformat()
} for u in random.sample(users, int(NUM_USERS * 0.8))] # 80% of users have tokens

# Chats & Participants
chats = []
participants = []
chat_user_map = {} # To keep track of who is in which chat for messaging

# Direct Chats (Strictly 2 participants)
for _ in range(NUM_DIRECT_CHATS):
    chat_id = f"chat_d_{uuid.uuid4().hex[:10]}"
    chats.append({'id': chat_id, 'type': 'direct'})
    
    chat_users = random.sample(user_ids, 2)
    chat_user_map[chat_id] = chat_users
    for uid in chat_users:
        participants.append({'chat_id': chat_id, 'user_id': uid})

# Group Chats (3 to 10 participants)
groups = [] # For Neo4j Group nodes
for _ in range(NUM_GROUP_CHATS):
    chat_id = f"chat_g_{uuid.uuid4().hex[:10]}"
    group_id = f"grp_{uuid.uuid4().hex[:12]}"
    chats.append({'id': chat_id, 'type': 'group'})

    chat_users = random.sample(user_ids, random.randint(3, 10))
    owner_id = chat_users[0]
    groups.append({
        'id': group_id,
        'psqlChatId': chat_id,
        'ownerId': owner_id,
        'name': fake.company() + " Fan Club",
        'description': fake.catch_phrase()
    })

    chat_user_map[chat_id] = chat_users
    for uid in chat_users:
        participants.append({'chat_id': chat_id, 'user_id': uid})

# Messages (Enforcing sender is participant)
messages = []
for chat_id, u_ids in chat_user_map.items():
    for _ in range(random.randint(1, MESSAGES_PER_CHAT_MAX)):
        messages.append({
            'id': f"msg_{uuid.uuid4().hex[:16]}",
            'chat_id': chat_id,
            'sender_id': random.choice(u_ids),
            'message': fake.sentence(),
            'created_at': fake.date_time_this_month().isoformat()
        })

# Music Entities (For Neo4j)
artists = [{'id': f"artist_{uuid.uuid4().hex[:8]}", 'name': fake.name(), 'profilePicture': fake.image_url(), 'spotifyURL': fake.url()} for _ in range(NUM_ARTISTS)]
artist_ids = [a['id'] for a in artists]

songs = [{'id': f"song_{uuid.uuid4().hex[:8]}", 'title': fake.catch_phrase(), 'coverURL': fake.image_url(), 'spotifyURL': fake.url()} for _ in range(NUM_SONGS)]
song_ids = [s['id'] for s in songs]

genres = [{'id': f"genre_{i}", 'name': name} for i, name in enumerate(GENRES)]
genre_ids = [g['id'] for g in genres]

# ==========================================
# 2. GENERATE NEO4J RELATIONSHIPS
# ==========================================
print("Generating Relationships...")

friends_rels = []
for u_id in user_ids:
    # 0 to 5 friends per user
    friends = random.sample(user_ids, random.randint(0, 5))
    for f_id in friends:
        if u_id != f_id:
            friends_rels.append({'from': u_id, 'to': f_id, 'closeness': round(random.uniform(0.1, 1.0), 2)})

listen_rels = []
for u_id in user_ids:
    for s_id in random.sample(song_ids, random.randint(1, 10)):
        listen_rels.append({
            'user_id': u_id, 'song_id': s_id,
            'short': random.randint(0, 100), 'medium': random.randint(50, 300), 'long': random.randint(100, 1000)
        })

song_artist_rels = [{'song_id': s['id'], 'artist_id': random.choice(artist_ids)} for s in songs]
song_genre_rels = [{'song_id': s['id'], 'genre_id': random.choice(genre_ids)} for s in songs]

# Filter group chat participants specifically for Neo4j PARTS_OF
group_chat_ids = [g['psqlChatId'] for g in groups]
group_owners = {g['psqlChatId']: g['ownerId'] for g in groups}
parts_of_rels = [
    {
        **p,
        'role': 'owner' if p['user_id'] == group_owners[p['chat_id']] else 'member',
        'joined_at': datetime.now().isoformat(),
    }
    for p in participants
    if p['chat_id'] in group_chat_ids
]

# ==========================================
# 3. WRITE TO FILES
# ==========================================
# PostgreSQL Files
write_csv('psql_users.csv', users, ['id', 'username', 'email', 'password_hash', 'avatar_url', 'bio'])
write_csv('psql_refresh_tokens.csv', tokens, ['token_hash', 'user_id', 'created_at'])
write_csv('psql_chats.csv', chats, ['id', 'type'])
write_csv('psql_chat_participants.csv', participants, ['chat_id', 'user_id'])
write_csv('psql_chat_messages.csv', messages, ['id', 'chat_id', 'sender_id', 'message', 'created_at'])

# Neo4j Nodes
write_csv('neo4j_users.csv', [{'psqlId': u['id'], 'username': u['username']} for u in users], ['psqlId', 'username'])
write_csv('neo4j_groups.csv', groups, ['id', 'psqlChatId', 'ownerId', 'name', 'description'])
write_csv('neo4j_artists.csv', artists, ['id', 'name', 'profilePicture', 'spotifyURL'])
write_csv('neo4j_songs.csv', songs, ['id', 'title', 'coverURL', 'spotifyURL'])
write_csv('neo4j_genres.csv', genres, ['id', 'name'])

# Neo4j Relationships
write_csv('neo4j_rel_friends.csv', friends_rels, ['from', 'to', 'closeness'])
write_csv('neo4j_rel_listen.csv', listen_rels, ['user_id', 'song_id', 'short', 'medium', 'long'])
write_csv('neo4j_rel_song_artist.csv', song_artist_rels, ['song_id', 'artist_id'])
write_csv('neo4j_rel_song_genre.csv', song_genre_rels, ['song_id', 'genre_id'])
write_csv('neo4j_rel_parts_of.csv', parts_of_rels, ['chat_id', 'user_id', 'role', 'joined_at'])

print("Successfully generated all CSVs!")
