// ==========================================
// 2. IMPORT NODES
// ==========================================

// Import Users
LOAD CSV WITH HEADERS FROM 'file:///neo4j_users.csv' AS row
CREATE (:User {psqlId: row.psqlId, username: row.username});

// Import Groups
LOAD CSV WITH HEADERS FROM 'file:///neo4j_groups.csv' AS row
CREATE (:Group {psqlChatId: row.psqlChatId, name: row.name, description: row.description});

// Import Artists
LOAD CSV WITH HEADERS FROM 'file:///neo4j_artists.csv' AS row
CREATE (:Artists {id: row.id, name: row.name, profilePicture: row.profilePicture, spotifyURL: row.spotifyURL});

// Import Songs
LOAD CSV WITH HEADERS FROM 'file:///neo4j_songs.csv' AS row
CREATE (:Song {id: row.id, title: row.title, coverURL: row.coverURL, spotifyURL: row.spotifyURL});

// Import Genres
LOAD CSV WITH HEADERS FROM 'file:///neo4j_genres.csv' AS row
CREATE (:Genre {id: row.id, name: row.name});

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
CREATE (u1)-[:FRIENDS_WITH {closeness: toFloat(row.closeness)}]->(u2);

// Listen To (User -> Song)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_listen.csv' AS row
MATCH (u:User {psqlId: row.user_id})
MATCH (s:Song {id: row.song_id})
CREATE (u)-[:LISTEN_TO {
    shortTermScore: toInteger(row.short), 
    mediumTermScore: toInteger(row.medium), 
    longTermScore: toInteger(row.long)
}]->(s);

// Performed By (Song -> Artist)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_song_artist.csv' AS row
MATCH (s:Song {id: row.song_id})
MATCH (a:Artists {id: row.artist_id})
CREATE (s)-[:PERFORMED_BY]->(a);

// Related To (Song -> Genre)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_song_genre.csv' AS row
MATCH (s:Song {id: row.song_id})
MATCH (g:Genre {id: row.genre_id})
CREATE (s)-[:RELATED_TO]->(g);

// Parts Of (User -> Group)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rel_parts_of.csv' AS row
MATCH (u:User {psqlId: row.user_id})
MATCH (grp:Group {psqlChatId: row.chat_id})
CREATE (u)-[:PARTS_OF]->(grp);
