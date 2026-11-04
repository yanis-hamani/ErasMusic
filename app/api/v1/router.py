from fastapi import APIRouter
from app.api.v1 import auth
# from app.api.v1 import auth, users, friends, groups, music, recommendations, search, chats

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentification"])
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(friends.router, tags=["Friends"])
# api_router.include_router(groups.router, prefix="/groups", tags=["Groups"])
# api_router.include_router(music.router, tags=["Music"])
# api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
# api_router.include_router(search.router, prefix="/search", tags=["Search"])
# api_router.include_router(chats.router, prefix="/chats", tags=["Chats"])
