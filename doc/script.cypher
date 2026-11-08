// 1. Create sample nodes with their respective properties
CREATE 
  (u1:User {psqlId: 'user_001'}),
  (u2:User {psqlId: 'user_002'}),
  (u3:User {psqlId: 'user_003'}),
  (s:Song {id: 'song_001', title: 'Example Song', coverURL: 'https://...', spotifyURL: 'https://...'}),
  (a:Artists {id: 'artist_001', name: 'Example Artist', profilePicture: 'https://...', spotifyURL: 'https://...'}),
  (g:Genre {id: 'genre_001', name: 'Synthwave'}),
  (grp:Group {psqlChatId: 'chat_001', name: 'Music Enthusiasts', description: 'A group for sharing music'})

// 2. Create relationships between the User nodes
CREATE (u1)-[:FRIENDS_WITH {closeness: 0.95}]->(u2)
CREATE (u1)-[:REQUESTED_FRIENDSHIP]->(u3)

// 3. Create relationships from User to other entities
CREATE (u1)-[:LISTEN_TO {shortTermScore: 85, mediumTermScore: 120, longTermScore: 450}]->(s)
CREATE (u1)-[:STREAMS {shortTermScore: 40, mediumTermScore: 300, longTermScore: 1200}]->(a)
CREATE (u1)-[:LIKES]->(g)
CREATE (u1)-[:PARTS_OF]->(grp)

// 4. Create relationships from Song to other entities
CREATE (s)-[:PERFORMED_BY]->(a)
CREATE (s)-[:RELATED_TO]->(g)

// 5. Create relationships from Group to other entities
CREATE (grp)-[:TAGGED_WITH]->(g)
CREATE (grp)-[:TAGGED_WITH]->(a);

Constraint :

Group :
- psqlId UNIQUE NOT NULL
- name UNIQUE NOT NULL
- 10 tags max confondu

User :
- psqlId UNIQUE NOT NULL
- :friends_with closeness NOT NULL default 0
- Friends_with should be queried undirectionally !

Genre :
- id (uuid creer dans l'applicatif) UNIQUE NOT NULL
- name string

Song :
- id (uuid creer dans l'applicatif) UNIQUE NOT NULL
- title string

Artist :
- id (uuid creer dans l'applicatif) UNIQUE NOT NULL
- name string
