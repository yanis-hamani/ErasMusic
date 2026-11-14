from app.models.recommendations import RecommendationPeriod


class SpotifyNeoRepository:
    SCORE_PROPERTIES = {
        period.value: period.score_property for period in RecommendationPeriod
    }

    @classmethod
    async def replace_period_affinities(
        cls,
        transaction,
        user_id: str,
        period: str,
        tracks: list[dict],
        artists: list[dict],
    ) -> None:
        score_property = cls.SCORE_PROPERTIES[period]
        await transaction.run(
            f"""
            MATCH (user:User {{psqlId: $user_id}})
            OPTIONAL MATCH (user)-[listen:LISTEN_TO]->(:Song)
            SET listen.{score_property} = 0
            WITH user
            OPTIONAL MATCH (user)-[preference:TOP_ARTIST]->(:Artists)
            SET preference.{score_property} = 0
            """,
            user_id=user_id,
        )
        await transaction.run(
            f"""
            MATCH (user:User {{psqlId: $user_id}})
            UNWIND $tracks AS item
            MERGE (song:Song {{id: item.id}})
            SET song.title = item.title,
                song.coverURL = item.coverUrl,
                song.spotifyURL = item.spotifyUrl
            MERGE (user)-[listen:LISTEN_TO]->(song)
            SET listen.{score_property} = item.score
            WITH song, item
            UNWIND item.artists AS artistData
            MERGE (artist:Artists {{id: artistData.id}})
            SET artist.name = artistData.name,
                artist.spotifyURL = artistData.spotifyUrl,
                artist.profilePicture = coalesce(
                    artistData.profilePictureUrl,
                    artist.profilePicture
                )
            MERGE (song)-[:PERFORMED_BY]->(artist)
            """,
            user_id=user_id,
            tracks=tracks,
        )
        await transaction.run(
            f"""
            MATCH (user:User {{psqlId: $user_id}})
            UNWIND $artists AS item
            MERGE (artist:Artists {{id: item.id}})
            SET artist.name = item.name,
                artist.profilePicture = coalesce(
                    item.profilePictureUrl,
                    artist.profilePicture
                ),
                artist.spotifyURL = item.spotifyUrl
            MERGE (user)-[preference:TOP_ARTIST]->(artist)
            SET preference.{score_property} = item.score
            WITH artist, item
            UNWIND item.genres AS genreData
            MERGE (genre:Genre {{normalizedName: genreData.normalizedName}})
            ON CREATE SET genre.id = genreData.id
            SET genre.name = genreData.name
            MERGE (artist)-[:RELATED_TO]->(genre)
            """,
            user_id=user_id,
            artists=artists,
        )
        await transaction.run(
            """
            UNWIND $tracks AS item
            MATCH (song:Song {id: item.id})
            UNWIND item.genres AS genreData
            MERGE (genre:Genre {normalizedName: genreData.normalizedName})
            ON CREATE SET genre.id = genreData.id
            SET genre.name = genreData.name
            MERGE (song)-[:RELATED_TO]->(genre)
            """,
            tracks=tracks,
        )

    @staticmethod
    async def cleanup_empty_affinities(transaction, user_id: str) -> None:
        await transaction.run(
            """
            MATCH (:User {psqlId: $user_id})-[relationship:LISTEN_TO|TOP_ARTIST]->()
            WHERE coalesce(relationship.shortTermScore, 0) = 0
              AND coalesce(relationship.mediumTermScore, 0) = 0
              AND coalesce(relationship.longTermScore, 0) = 0
            DELETE relationship
            """,
            user_id=user_id,
        )

    @staticmethod
    async def delete_user_affinities(transaction, user_id: str) -> None:
        await transaction.run(
            """
            MATCH (:User {psqlId: $user_id})-[relationship:LISTEN_TO|TOP_ARTIST]->()
            DELETE relationship
            """,
            user_id=user_id,
        )
