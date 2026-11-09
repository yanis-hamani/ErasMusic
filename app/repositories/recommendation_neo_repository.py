from datetime import datetime

from app.models.groups import ArtistGroupTag, GenreGroupTag, Group
from app.models.music import Artist, Genre, Song
from app.models.recommendations import (
    ArtistGroupRecommendations,
    ArtistUserRecommendations,
    FriendGroupRecommendations,
    FriendUserRecommendations,
    GenreGroupRecommendations,
    SongUserRecommendations,
)
from app.models.search import SearchUser


class RecommendationNeoRepository:
    @staticmethod
    def _effective_closeness(relationship: str) -> str:
        return f"""
            coalesce({relationship}.closeness, 0.0)
            * (2.0 ^ (0.0 - CASE
                WHEN {relationship}.closenessUpdatedAt IS NULL THEN 0.0
                WHEN toFloat(
                    asOf.epochSeconds
                    - {relationship}.closenessUpdatedAt.epochSeconds
                ) / 2592000.0 < 0.0 THEN 0.0
                ELSE toFloat(
                    asOf.epochSeconds
                    - {relationship}.closenessUpdatedAt.epochSeconds
                ) / 2592000.0
            END))
        """

    @staticmethod
    async def count_friend_recommendations_by_artists(
        transaction,
        user_id: str,
        score_property: str,
    ) -> int:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[currentListen:LISTEN_TO]->(:Song)
                  -[:PERFORMED_BY]->(artist:Artists)
            WHERE coalesce(currentListen[$score_property], 0) > 0
            WITH DISTINCT current, artist
            MATCH (candidate:User)-[candidateListen:LISTEN_TO]->(:Song)
                  -[:PERFORMED_BY]->(artist)
            WHERE coalesce(candidateListen[$score_property], 0) > 0
              AND candidate <> current
              AND NOT EXISTS {
                  MATCH (current)-[:FRIENDS_WITH]-(candidate)
              }
            RETURN count(DISTINCT artist) AS total
            """,
            user_id=user_id,
            score_property=score_property,
        )
        return RecommendationNeoRepository._total(await result.single())

    @staticmethod
    async def list_friend_recommendations_by_artists(
        transaction,
        user_id: str,
        score_property: str,
        skip: int,
        limit: int,
    ) -> list[ArtistUserRecommendations]:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[currentListen:LISTEN_TO]->(:Song)
                  -[:PERFORMED_BY]->(artist:Artists)
            WHERE coalesce(currentListen[$score_property], 0) > 0
            WITH current,
                 artist,
                 sum(toFloat(currentListen[$score_property])) AS currentAffinity
            MATCH (candidate:User)-[candidateListen:LISTEN_TO]->(:Song)
                  -[:PERFORMED_BY]->(artist)
            WHERE coalesce(candidateListen[$score_property], 0) > 0
              AND candidate <> current
              AND NOT EXISTS {
                  MATCH (current)-[:FRIENDS_WITH]-(candidate)
              }
            WITH artist,
                 currentAffinity,
                 candidate,
                 sum(toFloat(candidateListen[$score_property])) AS candidateAffinity
            ORDER BY currentAffinity DESC,
                     artist.id,
                     candidateAffinity DESC,
                     toLower(candidate.username),
                     candidate.psqlId
            WITH artist,
                 currentAffinity,
                 collect({
                     id: candidate.psqlId,
                     username: candidate.username
                 })[0..20] AS users
            RETURN artist.id AS artistId,
                   artist.name AS artistName,
                   artist.profilePicture AS profilePictureUrl,
                   artist.spotifyURL AS spotifyUrl,
                   users
            ORDER BY currentAffinity DESC, artist.id
            SKIP $skip
            LIMIT $limit
            """,
            user_id=user_id,
            score_property=score_property,
            skip=skip,
            limit=limit,
        )
        return [
            RecommendationNeoRepository._artist_user_bucket(record)
            async for record in result
        ]

    @staticmethod
    async def count_friend_recommendations_by_songs(
        transaction,
        user_id: str,
        score_property: str,
    ) -> int:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[currentListen:LISTEN_TO]->(song:Song)
            WHERE coalesce(currentListen[$score_property], 0) > 0
            WITH DISTINCT current, song
            MATCH (candidate:User)-[candidateListen:LISTEN_TO]->(song)
            WHERE coalesce(candidateListen[$score_property], 0) > 0
              AND candidate <> current
              AND NOT EXISTS {
                  MATCH (current)-[:FRIENDS_WITH]-(candidate)
              }
            RETURN count(DISTINCT song) AS total
            """,
            user_id=user_id,
            score_property=score_property,
        )
        return RecommendationNeoRepository._total(await result.single())

    @staticmethod
    async def list_friend_recommendations_by_songs(
        transaction,
        user_id: str,
        score_property: str,
        skip: int,
        limit: int,
    ) -> list[SongUserRecommendations]:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[currentListen:LISTEN_TO]->(song:Song)
            WHERE coalesce(currentListen[$score_property], 0) > 0
            WITH current,
                 song,
                 sum(toFloat(currentListen[$score_property])) AS currentAffinity
            MATCH (candidate:User)-[candidateListen:LISTEN_TO]->(song)
            WHERE coalesce(candidateListen[$score_property], 0) > 0
              AND candidate <> current
              AND NOT EXISTS {
                  MATCH (current)-[:FRIENDS_WITH]-(candidate)
              }
            WITH song,
                 currentAffinity,
                 candidate,
                 sum(toFloat(candidateListen[$score_property])) AS candidateAffinity
            ORDER BY currentAffinity DESC,
                     song.id,
                     candidateAffinity DESC,
                     toLower(candidate.username),
                     candidate.psqlId
            WITH song,
                 currentAffinity,
                 collect({
                     id: candidate.psqlId,
                     username: candidate.username
                 })[0..20] AS users
            ORDER BY currentAffinity DESC, song.id
            SKIP $skip
            LIMIT $limit
            OPTIONAL MATCH (song)-[:PERFORMED_BY]->(artist:Artists)
            WITH song, currentAffinity, users, artist
            ORDER BY toLower(artist.name), artist.id
            WITH song,
                 currentAffinity,
                 users,
                 collect(DISTINCT {
                     id: artist.id,
                     name: artist.name,
                     profilePictureUrl: artist.profilePicture,
                     spotifyUrl: artist.spotifyURL
                 }) AS artists
            RETURN song.id AS songId,
                   song.title AS songTitle,
                   song.coverURL AS coverUrl,
                   song.spotifyURL AS spotifyUrl,
                   artists,
                   users
            ORDER BY currentAffinity DESC, song.id
            """,
            user_id=user_id,
            score_property=score_property,
            skip=skip,
            limit=limit,
        )
        return [
            RecommendationNeoRepository._song_user_bucket(record)
            async for record in result
        ]

    @staticmethod
    async def count_friend_recommendations_by_friends(
        transaction,
        user_id: str,
    ) -> int:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})-[:FRIENDS_WITH]-(friend:User)
                  -[:FRIENDS_WITH]-(candidate:User)
            WHERE candidate <> current
              AND candidate <> friend
              AND NOT EXISTS {
                  MATCH (current)-[:FRIENDS_WITH]-(candidate)
              }
            RETURN count(DISTINCT friend) AS total
            """,
            user_id=user_id,
        )
        return RecommendationNeoRepository._total(await result.single())

    @staticmethod
    async def list_friend_recommendations_by_friends(
        transaction,
        user_id: str,
        as_of: datetime,
        skip: int,
        limit: int,
    ) -> list[FriendUserRecommendations]:
        first_closeness = RecommendationNeoRepository._effective_closeness(
            "firstFriendship"
        )
        second_closeness = RecommendationNeoRepository._effective_closeness(
            "secondFriendship"
        )
        query = """
            MATCH (current:User {psqlId: $user_id})
            WITH current, $as_of AS asOf
            MATCH (current)-[firstFriendship:FRIENDS_WITH]-(friend:User)
                  -[secondFriendship:FRIENDS_WITH]-(candidate:User)
            WHERE candidate <> current
              AND candidate <> friend
              AND NOT EXISTS {
                  MATCH (current)-[:FRIENDS_WITH]-(candidate)
              }
            WITH friend,
                 candidate,
                 __FIRST_CLOSENESS__ AS friendCloseness,
                 __SECOND_CLOSENESS__ AS candidateCloseness
            WITH friend,
                 candidate,
                 max(friendCloseness) AS friendCloseness,
                 max(friendCloseness * candidateCloseness) AS pathScore
            ORDER BY friendCloseness DESC,
                     friend.psqlId,
                     pathScore DESC,
                     toLower(candidate.username),
                     candidate.psqlId
            WITH friend,
                 friendCloseness,
                 collect({
                     id: candidate.psqlId,
                     username: candidate.username
                 })[0..20] AS users
            RETURN friend.psqlId AS friendId,
                   friend.username AS friendUsername,
                   users
            ORDER BY friendCloseness DESC, friend.psqlId
            SKIP $skip
            LIMIT $limit
        """
        query = query.replace("__FIRST_CLOSENESS__", first_closeness).replace(
            "__SECOND_CLOSENESS__",
            second_closeness,
        )
        result = await transaction.run(
            query,
            user_id=user_id,
            as_of=as_of,
            skip=skip,
            limit=limit,
        )
        return [
            RecommendationNeoRepository._friend_user_bucket(record)
            async for record in result
        ]

    @staticmethod
    async def count_group_recommendations_by_artists(
        transaction,
        user_id: str,
        score_property: str,
    ) -> int:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[listen:LISTEN_TO]->(:Song)
                  -[:PERFORMED_BY]->(artist:Artists)
            WHERE coalesce(listen[$score_property], 0) > 0
            WITH DISTINCT current, artist
            MATCH (group:Group)-[:TAGGED_WITH]->(artist)
            WHERE group.id IS NOT NULL
              AND NOT EXISTS {
                  MATCH (current)-[:PARTS_OF]->(group)
              }
            RETURN count(DISTINCT artist) AS total
            """,
            user_id=user_id,
            score_property=score_property,
        )
        return RecommendationNeoRepository._total(await result.single())

    @staticmethod
    async def list_group_recommendations_by_artists(
        transaction,
        user_id: str,
        score_property: str,
        skip: int,
        limit: int,
    ) -> list[ArtistGroupRecommendations]:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[listen:LISTEN_TO]->(:Song)
                  -[:PERFORMED_BY]->(artist:Artists)
            WHERE coalesce(listen[$score_property], 0) > 0
            WITH current,
                 artist,
                 sum(toFloat(listen[$score_property])) AS currentAffinity
            MATCH (group:Group)-[:TAGGED_WITH]->(artist)
            WHERE group.id IS NOT NULL
              AND NOT EXISTS {
                  MATCH (current)-[:PARTS_OF]->(group)
              }
            OPTIONAL MATCH (group)-[:TAGGED_WITH]->(tag)
            WITH artist, currentAffinity, group, tag
            ORDER BY CASE WHEN 'Artists' IN labels(tag) THEN 0 ELSE 1 END,
                     toLower(tag.name),
                     tag.id
            WITH artist,
                 currentAffinity,
                 group,
                 collect(DISTINCT CASE
                     WHEN tag IS NULL THEN null
                     ELSE {labels: labels(tag), id: tag.id, name: tag.name}
                 END) AS tags
            ORDER BY currentAffinity DESC,
                     artist.id,
                     toLower(group.name),
                     group.id
            WITH artist,
                 currentAffinity,
                 collect({
                     id: group.id,
                     ownerId: group.ownerId,
                     name: group.name,
                     description: group.description,
                     tags: tags
                 })[0..20] AS groups
            RETURN artist.id AS artistId,
                   artist.name AS artistName,
                   artist.profilePicture AS profilePictureUrl,
                   artist.spotifyURL AS spotifyUrl,
                   groups
            ORDER BY currentAffinity DESC, artist.id
            SKIP $skip
            LIMIT $limit
            """,
            user_id=user_id,
            score_property=score_property,
            skip=skip,
            limit=limit,
        )
        return [
            RecommendationNeoRepository._artist_group_bucket(record)
            async for record in result
        ]

    @staticmethod
    async def count_group_recommendations_by_genres(
        transaction,
        user_id: str,
        score_property: str,
    ) -> int:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[listen:LISTEN_TO]->(:Song)
                  -[:RELATED_TO]->(genre:Genre)
            WHERE coalesce(listen[$score_property], 0) > 0
            WITH DISTINCT current, genre
            MATCH (group:Group)-[:TAGGED_WITH]->(genre)
            WHERE group.id IS NOT NULL
              AND NOT EXISTS {
                  MATCH (current)-[:PARTS_OF]->(group)
              }
            RETURN count(DISTINCT genre) AS total
            """,
            user_id=user_id,
            score_property=score_property,
        )
        return RecommendationNeoRepository._total(await result.single())

    @staticmethod
    async def list_group_recommendations_by_genres(
        transaction,
        user_id: str,
        score_property: str,
        skip: int,
        limit: int,
    ) -> list[GenreGroupRecommendations]:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})
                  -[listen:LISTEN_TO]->(:Song)
                  -[:RELATED_TO]->(genre:Genre)
            WHERE coalesce(listen[$score_property], 0) > 0
            WITH current,
                 genre,
                 sum(toFloat(listen[$score_property])) AS currentAffinity
            MATCH (group:Group)-[:TAGGED_WITH]->(genre)
            WHERE group.id IS NOT NULL
              AND NOT EXISTS {
                  MATCH (current)-[:PARTS_OF]->(group)
              }
            OPTIONAL MATCH (group)-[:TAGGED_WITH]->(tag)
            WITH genre, currentAffinity, group, tag
            ORDER BY CASE WHEN 'Artists' IN labels(tag) THEN 0 ELSE 1 END,
                     toLower(tag.name),
                     tag.id
            WITH genre,
                 currentAffinity,
                 group,
                 collect(DISTINCT CASE
                     WHEN tag IS NULL THEN null
                     ELSE {labels: labels(tag), id: tag.id, name: tag.name}
                 END) AS tags
            ORDER BY currentAffinity DESC,
                     genre.id,
                     toLower(group.name),
                     group.id
            WITH genre,
                 currentAffinity,
                 collect({
                     id: group.id,
                     ownerId: group.ownerId,
                     name: group.name,
                     description: group.description,
                     tags: tags
                 })[0..20] AS groups
            RETURN genre.id AS genreId,
                   genre.name AS genreName,
                   groups
            ORDER BY currentAffinity DESC, genre.id
            SKIP $skip
            LIMIT $limit
            """,
            user_id=user_id,
            score_property=score_property,
            skip=skip,
            limit=limit,
        )
        return [
            RecommendationNeoRepository._genre_group_bucket(record)
            async for record in result
        ]

    @staticmethod
    async def count_group_recommendations_by_friends(
        transaction,
        user_id: str,
    ) -> int:
        result = await transaction.run(
            """
            MATCH (current:User {psqlId: $user_id})-[:FRIENDS_WITH]-(friend:User)
                  -[:PARTS_OF]->(group:Group)
            WHERE group.id IS NOT NULL
              AND NOT EXISTS {
                  MATCH (current)-[:PARTS_OF]->(group)
              }
            RETURN count(DISTINCT friend) AS total
            """,
            user_id=user_id,
        )
        return RecommendationNeoRepository._total(await result.single())

    @staticmethod
    async def list_group_recommendations_by_friends(
        transaction,
        user_id: str,
        as_of: datetime,
        skip: int,
        limit: int,
    ) -> list[FriendGroupRecommendations]:
        closeness = RecommendationNeoRepository._effective_closeness("friendship")
        query = """
            MATCH (current:User {psqlId: $user_id})
            WITH current, $as_of AS asOf
            MATCH (current)-[friendship:FRIENDS_WITH]-(friend:User)
                  -[:PARTS_OF]->(group:Group)
            WHERE group.id IS NOT NULL
              AND NOT EXISTS {
                  MATCH (current)-[:PARTS_OF]->(group)
              }
            WITH friend,
                 group,
                 max(__CLOSENESS__) AS friendCloseness
            OPTIONAL MATCH (group)-[:TAGGED_WITH]->(tag)
            WITH friend, friendCloseness, group, tag
            ORDER BY CASE WHEN 'Artists' IN labels(tag) THEN 0 ELSE 1 END,
                     toLower(tag.name),
                     tag.id
            WITH friend,
                 friendCloseness,
                 group,
                 collect(DISTINCT CASE
                     WHEN tag IS NULL THEN null
                     ELSE {labels: labels(tag), id: tag.id, name: tag.name}
                 END) AS tags
            ORDER BY friendCloseness DESC,
                     friend.psqlId,
                     toLower(group.name),
                     group.id
            WITH friend,
                 friendCloseness,
                 collect({
                     id: group.id,
                     ownerId: group.ownerId,
                     name: group.name,
                     description: group.description,
                     tags: tags
                 })[0..20] AS groups
            RETURN friend.psqlId AS friendId,
                   friend.username AS friendUsername,
                   groups
            ORDER BY friendCloseness DESC, friend.psqlId
            SKIP $skip
            LIMIT $limit
        """.replace("__CLOSENESS__", closeness)
        result = await transaction.run(
            query,
            user_id=user_id,
            as_of=as_of,
            skip=skip,
            limit=limit,
        )
        return [
            RecommendationNeoRepository._friend_group_bucket(record)
            async for record in result
        ]

    @staticmethod
    def _total(record) -> int:
        return int(record["total"]) if record else 0

    @staticmethod
    def _user(data) -> SearchUser:
        return SearchUser(id=data["id"], username=data["username"])

    @staticmethod
    def _artist_from_record(record) -> Artist:
        return Artist(
            id=record["artistId"],
            name=record["artistName"],
            profilePictureUrl=record["profilePictureUrl"] or None,
            spotifyUrl=record["spotifyUrl"] or None,
        )

    @staticmethod
    def _artist_from_map(data) -> Artist:
        return Artist(
            id=data["id"],
            name=data["name"],
            profilePictureUrl=data.get("profilePictureUrl") or None,
            spotifyUrl=data.get("spotifyUrl") or None,
        )

    @staticmethod
    def _group(data) -> Group:
        tags = []
        for tag in data.get("tags") or []:
            if not tag or not tag.get("id"):
                continue
            if "Artists" in (tag.get("labels") or []):
                tags.append(
                    ArtistGroupTag(
                        type="artist",
                        artistId=tag["id"],
                        name=tag["name"],
                    )
                )
            else:
                tags.append(
                    GenreGroupTag(
                        type="genre",
                        genreId=tag["id"],
                        name=tag["name"],
                    )
                )
        return Group(
            id=data["id"],
            ownerId=data["ownerId"],
            name=data["name"],
            description=data["description"],
            tags=tags,
        )

    @staticmethod
    def _artist_user_bucket(record) -> ArtistUserRecommendations:
        return ArtistUserRecommendations(
            artist=RecommendationNeoRepository._artist_from_record(record),
            users=[RecommendationNeoRepository._user(user) for user in record["users"]],
        )

    @staticmethod
    def _song_user_bucket(record) -> SongUserRecommendations:
        song = Song(
            id=record["songId"],
            title=record["songTitle"],
            coverUrl=record["coverUrl"] or None,
            spotifyUrl=record["spotifyUrl"] or None,
            artists=[
                RecommendationNeoRepository._artist_from_map(artist)
                for artist in (record["artists"] or [])
                if artist and artist.get("id")
            ],
        )
        return SongUserRecommendations(
            song=song,
            users=[RecommendationNeoRepository._user(user) for user in record["users"]],
        )

    @staticmethod
    def _friend_user_bucket(record) -> FriendUserRecommendations:
        return FriendUserRecommendations(
            friend=SearchUser(
                id=record["friendId"],
                username=record["friendUsername"],
            ),
            users=[RecommendationNeoRepository._user(user) for user in record["users"]],
        )

    @staticmethod
    def _artist_group_bucket(record) -> ArtistGroupRecommendations:
        return ArtistGroupRecommendations(
            artist=RecommendationNeoRepository._artist_from_record(record),
            groups=[RecommendationNeoRepository._group(group) for group in record["groups"]],
        )

    @staticmethod
    def _genre_group_bucket(record) -> GenreGroupRecommendations:
        return GenreGroupRecommendations(
            genre=Genre(id=record["genreId"], name=record["genreName"]),
            groups=[RecommendationNeoRepository._group(group) for group in record["groups"]],
        )

    @staticmethod
    def _friend_group_bucket(record) -> FriendGroupRecommendations:
        return FriendGroupRecommendations(
            friend=SearchUser(
                id=record["friendId"],
                username=record["friendUsername"],
            ),
            groups=[RecommendationNeoRepository._group(group) for group in record["groups"]],
        )
