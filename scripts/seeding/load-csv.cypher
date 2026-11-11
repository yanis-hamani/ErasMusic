// ==========================================
// 2. IMPORT NODES
// ==========================================

// Import Users
LOAD CSV WITH HEADERS FROM 'file:///neo4j_users.csv' AS row
MERGE (user:User {psqlId: row.psqlId})
SET user.username = row.username;

// Import Groups
LOAD CSV WITH HEADERS FROM 'file:///neo4j_groups.csv' AS row
MERGE (group:Group {psqlChatId: row.psqlChatId})
SET group.id = coalesce(row.id, 'grp_' + replace(row.psqlChatId, 'chat_', '')),
    group.ownerId = coalesce(row.ownerId, group.ownerId),
    group.name = row.name,
    group.description = row.description;

// Import Artists
LOAD CSV WITH HEADERS FROM 'file:///neo4j_artists.csv' AS row
MERGE (artist:Artists {id: row.id})
SET artist.name = row.name,
    artist.profilePicture = row.profilePicture,
    artist.spotifyURL = row.spotifyURL;

// Import Songs
LOAD CSV WITH HEADERS FROM 'file:///neo4j_songs.csv' AS row
MERGE (song:Song {id: row.id})
SET song.title = row.title,
    song.coverURL = row.coverURL,
    song.spotifyURL = row.spotifyURL;

// Import Genres
LOAD CSV WITH HEADERS FROM 'file:///neo4j_genres.csv' AS row
MERGE (genre:Genre {id: row.id})
SET genre.name = row.name;

// ==========================================
// 3. IMPORT RELATIONSHIPS
// ==========================================
// We use USING PERIODIC COMMIT for massive files in Neo4j 4.x, 
// or CALL { ... } IN TRANSACTIONS for Neo4j 5.x. 
// For typical seeded batches (10k-100k), standard LOAD CSV is usually fine.

// Friends (User -> User)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_friends.csv' AS row
MATCH (u1:User {psqlId: row.from})
MATCH (u2:User {psqlId: row.to})
MERGE (u1)-[friendship:FRIENDS_WITH]-(u2)
ON CREATE SET friendship.closeness = toFloat(row.closeness),
              friendship.closenessUpdatedAt = datetime();

// Listen To (User -> Song)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_listen.csv' AS row
MATCH (u:User {psqlId: row.user_id})
MATCH (s:Song {id: row.song_id})
MERGE (u)-[listen:LISTEN_TO]->(s)
SET listen.shortTermScore = toInteger(row.short),
    listen.mediumTermScore = toInteger(row.medium),
    listen.longTermScore = toInteger(row.long);

// Performed By (Song -> Artist)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_song_artist.csv' AS row
MATCH (s:Song {id: row.song_id})
MATCH (a:Artists {id: row.artist_id})
MERGE (s)-[:PERFORMED_BY]->(a);

// Related To (Song -> Genre)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_song_genre.csv' AS row
MATCH (s:Song {id: row.song_id})
MATCH (g:Genre {id: row.genre_id})
MERGE (s)-[:RELATED_TO]->(g);

// Parts Of (User -> Group)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_parts_of.csv' AS row
MATCH (u:User {psqlId: row.user_id})
MATCH (grp:Group {psqlChatId: row.chat_id})
MERGE (u)-[membership:PARTS_OF]->(grp)
ON CREATE SET membership.role = coalesce(row.role, 'member'),
              membership.joinedAt = CASE
        WHEN row.joined_at IS NULL THEN datetime()
        ELSE datetime(row.joined_at)
    END;

// Group artist tags
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_group_tags.csv' AS row
WITH row WHERE row.tag_type = 'artist'
MATCH (group:Group {psqlChatId: row.chat_id})
MATCH (artist:Artists {id: row.tag_id})
MERGE (group)-[:TAGGED_WITH]->(artist);

// Group genre tags
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_group_tags.csv' AS row
WITH row WHERE row.tag_type = 'genre'
MATCH (group:Group {psqlChatId: row.chat_id})
MATCH (genre:Genre {id: row.tag_id})
MERGE (group)-[:TAGGED_WITH]->(genre);

// Backfill ownership for legacy seed CSVs that do not contain owner metadata.
MATCH (user:User)-[membership:PARTS_OF]->(group:Group)
WITH group, user, membership
ORDER BY user.psqlId
WITH group, collect(user)[0] AS owner, collect(membership)[0] AS ownerMembership
WHERE group.ownerId IS NULL
SET group.ownerId = owner.psqlId,
    ownerMembership.role = 'owner';
