from app.repositories.user_psql_repository import UserPsqlRepository
from app.repositories.register_hashed_repository import RegisterHashedRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.core.database import init_pg_pool, init_neo4j_driver
from app.services.auth_services import AuthService
from app.services.user_services import UserService
from app.services.friend_services import FriendService
from app.repositories.friend_neo_repository import FriendNeoRepository
from app.repositories.group_neo_repository import GroupNeoRepository
from app.repositories.chat_psql_repository import ChatPsqlRepository
from app.services.group_services import GroupService
from app.services.search_services import SearchService
from app.repositories.music_neo_repository import MusicNeoRepository
from app.services.music_services import MusicService
from app.services.chat_services import ChatService
from app.repositories.recommendation_neo_repository import RecommendationNeoRepository
from app.services.recommendation_services import RecommendationService
from app.repositories.user_neo_repository import UserNeoRepository
from dishka import Provider, Scope, provide

class AppProvider(Provider):
    pg_pool = provide(staticmethod(init_pg_pool), scope=Scope.APP)
    neo4j_driver = provide(staticmethod(init_neo4j_driver), scope=Scope.APP)
     
    # Dishka looks at the __init__ type hints and wires them automatically
    user_neo_repo = provide(UserNeoRepository, scope=Scope.REQUEST)
    refresh_token_repo = provide(RefreshTokenRepository, scope=Scope.REQUEST)
    register_hashed_repo = provide(RegisterHashedRepository, scope=Scope.REQUEST)
    user_psql_repo = provide(UserPsqlRepository, scope=Scope.REQUEST)
    friend_neo_repo = provide(FriendNeoRepository, scope=Scope.REQUEST)
    group_neo_repo = provide(GroupNeoRepository, scope=Scope.REQUEST)
    chat_psql_repo = provide(ChatPsqlRepository, scope=Scope.REQUEST)
    music_neo_repo = provide(MusicNeoRepository, scope=Scope.REQUEST)
    recommendation_neo_repo = provide(
        RecommendationNeoRepository,
        scope=Scope.REQUEST,
    )

    auth_service = provide(AuthService, scope=Scope.REQUEST)
    user_service = provide(UserService, scope=Scope.REQUEST)
    friend_service = provide(FriendService, scope=Scope.REQUEST)
    group_service = provide(GroupService, scope=Scope.REQUEST)
    search_service = provide(SearchService, scope=Scope.REQUEST)
    music_service = provide(MusicService, scope=Scope.REQUEST)
    chat_service = provide(ChatService, scope=Scope.REQUEST)
    recommendation_service = provide(RecommendationService, scope=Scope.REQUEST)
