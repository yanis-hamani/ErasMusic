from app.models.music import Artist, Genre, Song


class MusicNeoRepository:
    @staticmethod
    async def count_artists(transaction) -> int:
        result = await transaction.run(
            "MATCH (artist:Artists) RETURN count(artist) AS total"
        )
        record = await result.single()
        return int(record["total"]) if record else 0

    @staticmethod
    async def list_artists(transaction, skip: int, limit: int) -> list[Artist]:
        result = await transaction.run(
            """
            MATCH (artist:Artists)
            RETURN artist.id AS id,
                   artist.name AS name,
                   artist.profilePicture AS profilePictureUrl,
                   artist.spotifyURL AS spotifyUrl
            ORDER BY toLower(artist.name), artist.id
            SKIP $skip
            LIMIT $limit
            """,
            skip=skip,
            limit=limit,
        )
        return [MusicNeoRepository._artist(record) async for record in result]

    @staticmethod
    async def select_artist(transaction, artist_id: str) -> Artist | None:
        result = await transaction.run(
            """
            MATCH (artist:Artists {id: $artist_id})
            RETURN artist.id AS id,
                   artist.name AS name,
                   artist.profilePicture AS profilePictureUrl,
                   artist.spotifyURL AS spotifyUrl
            """,
            artist_id=artist_id,
        )
        return MusicNeoRepository._artist(await result.single())

    @staticmethod
    async def count_songs(transaction) -> int:
        result = await transaction.run("MATCH (song:Song) RETURN count(song) AS total")
        record = await result.single()
        return int(record["total"]) if record else 0

    @staticmethod
    async def list_songs(transaction, skip: int, limit: int) -> list[Song]:
        result = await transaction.run(
            """
            MATCH (song:Song)
            WITH song
            ORDER BY toLower(song.title), song.id
            SKIP $skip
            LIMIT $limit
            OPTIONAL MATCH (song)-[:PERFORMED_BY]->(artist:Artists)
            WITH song, artist
            ORDER BY toLower(artist.name), artist.id
            WITH song, collect(DISTINCT artist {
                .id,
                .name,
                profilePictureUrl: artist.profilePicture,
                spotifyUrl: artist.spotifyURL
            }) AS artists
            RETURN song.id AS id,
                   song.title AS title,
                   song.coverURL AS coverUrl,
                   song.spotifyURL AS spotifyUrl,
                   artists
            ORDER BY toLower(song.title), song.id
            """,
            skip=skip,
            limit=limit,
        )
        return [MusicNeoRepository._song(record) async for record in result]

    @staticmethod
    async def select_song(transaction, song_id: str) -> Song | None:
        result = await transaction.run(
            """
            MATCH (song:Song {id: $song_id})
            OPTIONAL MATCH (song)-[:PERFORMED_BY]->(artist:Artists)
            WITH song, artist
            ORDER BY toLower(artist.name), artist.id
            WITH song, collect(DISTINCT artist {
                .id,
                .name,
                profilePictureUrl: artist.profilePicture,
                spotifyUrl: artist.spotifyURL
            }) AS artists
            RETURN song.id AS id,
                   song.title AS title,
                   song.coverURL AS coverUrl,
                   song.spotifyURL AS spotifyUrl,
                   artists
            """,
            song_id=song_id,
        )
        return MusicNeoRepository._song(await result.single())

    @staticmethod
    async def count_genres(transaction) -> int:
        result = await transaction.run(
            "MATCH (genre:Genre) RETURN count(genre) AS total"
        )
        record = await result.single()
        return int(record["total"]) if record else 0

    @staticmethod
    async def list_genres(transaction, skip: int, limit: int) -> list[Genre]:
        result = await transaction.run(
            """
            MATCH (genre:Genre)
            RETURN genre.id AS id, genre.name AS name
            ORDER BY toLower(genre.name), genre.id
            SKIP $skip
            LIMIT $limit
            """,
            skip=skip,
            limit=limit,
        )
        return [MusicNeoRepository._genre(record) async for record in result]

    @staticmethod
    async def select_genre(transaction, genre_id: str) -> Genre | None:
        result = await transaction.run(
            """
            MATCH (genre:Genre {id: $genre_id})
            RETURN genre.id AS id, genre.name AS name
            """,
            genre_id=genre_id,
        )
        return MusicNeoRepository._genre(await result.single())

    @staticmethod
    def _artist(record) -> Artist | None:
        if not record:
            return None
        return Artist(
            id=record["id"],
            name=record["name"],
            profilePictureUrl=record["profilePictureUrl"] or None,
            spotifyUrl=record["spotifyUrl"] or None,
        )

    @staticmethod
    def _song(record) -> Song | None:
        if not record:
            return None
        artists = [
            MusicNeoRepository._artist(artist)
            for artist in (record["artists"] or [])
            if artist
        ]
        return Song(
            id=record["id"],
            title=record["title"],
            coverUrl=record["coverUrl"] or None,
            spotifyUrl=record["spotifyUrl"] or None,
            artists=artists,
        )

    @staticmethod
    def _genre(record) -> Genre | None:
        if not record:
            return None
        return Genre(id=record["id"], name=record["name"])
