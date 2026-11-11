import os
import unittest


os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USERNAME", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-characters")

from app.main import app


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
EXPECTED_OPERATION_IDS = {
    "getHealth",
    "registerUser",
    "loginUser",
    "refreshAccessToken",
    "logoutUser",
    "getCurrentUserProfile",
    "updateCurrentUserProfile",
    "deleteCurrentUser",
    "getPublicUserProfile",
    "listFriends",
    "getFriendshipStatus",
    "removeFriend",
    "createFriendRequest",
    "listFriendRequests",
    "acceptFriendRequest",
    "declineFriendRequest",
    "listGroups",
    "createGroup",
    "getGroup",
    "updateGroup",
    "deleteGroup",
    "listGroupMembers",
    "addGroupMember",
    "leaveGroup",
    "listGroupTags",
    "replaceGroupTags",
    "listArtists",
    "getArtist",
    "listSongs",
    "getSong",
    "listGenres",
    "getGenre",
    "recommendFriendsByArtists",
    "recommendFriendsBySongs",
    "recommendFriendsByFriends",
    "recommendGroupsByArtists",
    "recommendGroupsByGenres",
    "recommendGroupsByFriends",
    "searchUsers",
    "searchGroups",
    "listChats",
    "createChat",
    "getChat",
    "listChatMessages",
    "sendChatMessage",
    "addChatMember",
    "leaveChat",
}
PUBLIC_OPERATIONS = {
    "getHealth",
    "registerUser",
    "loginUser",
    "refreshAccessToken",
}


class OpenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = app.openapi()
        cls.operations = {
            operation["operationId"]: operation
            for path in cls.schema["paths"].values()
            for method, operation in path.items()
            if method in HTTP_METHODS
        }

    def test_api_metadata_and_tags_are_documented(self):
        self.assertEqual("ErasMusic API", self.schema["info"]["title"])
        self.assertTrue(self.schema["info"]["description"])
        self.assertEqual(
            [{"url": "/", "description": "Current API base path"}],
            self.schema["servers"],
        )
        self.assertEqual(
            {
                "System",
                "Authentication",
                "User Profiles",
                "Friends & Social",
                "Groups",
                "Music Data",
                "Recommendations",
                "Search",
                "Chat",
            },
            {tag["name"] for tag in self.schema["tags"]},
        )
        self.assertTrue(all(tag.get("description") for tag in self.schema["tags"]))

    def test_operations_have_stable_ids_and_descriptions(self):
        self.assertEqual(EXPECTED_OPERATION_IDS, set(self.operations))
        self.assertEqual(len(EXPECTED_OPERATION_IDS), len(self.operations))
        for operation in self.operations.values():
            self.assertTrue(operation.get("summary"))
            self.assertTrue(operation.get("description"))
            self.assertTrue(operation.get("tags"))
            successful_responses = [
                response
                for code, response in operation["responses"].items()
                if code.startswith("2")
            ]
            self.assertTrue(successful_responses)
            self.assertTrue(
                all(response.get("description") for response in successful_responses)
            )

    def test_bearer_security_matches_runtime_dependencies(self):
        bearer = self.schema["components"]["securitySchemes"]["BearerAuth"]
        self.assertEqual("http", bearer["type"])
        self.assertEqual("bearer", bearer["scheme"])
        self.assertEqual("JWT", bearer["bearerFormat"])
        for operation_id, operation in self.operations.items():
            if operation_id in PUBLIC_OPERATIONS:
                self.assertNotIn("security", operation)
            else:
                self.assertEqual([{"BearerAuth": []}], operation.get("security"))

    def test_refresh_cookie_is_part_of_the_generated_contract(self):
        refresh = self.operations["refreshAccessToken"]
        cookie = next(
            parameter
            for parameter in refresh["parameters"]
            if parameter["name"] == "refresh_token"
        )
        self.assertEqual("cookie", cookie["in"])
        self.assertFalse(cookie["required"])

        register = self.operations["registerUser"]
        self.assertIn(
            "Set-Cookie",
            register["responses"]["201"]["headers"],
        )

    def test_generated_schemas_keep_documented_limits(self):
        schemas = self.schema["components"]["schemas"]
        self.assertEqual(
            20,
            schemas["ArtistUserRecommendations"]["properties"]["users"][
                "maxItems"
            ],
        )
        self.assertEqual(
            10,
            schemas["Group"]["properties"]["tags"]["maxItems"],
        )
        self.assertEqual(
            "password",
            schemas["RegisterRequest"]["properties"]["password"]["format"],
        )


if __name__ == "__main__":
    unittest.main()
