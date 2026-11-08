from app.core.di import AppProvider
from dishka.integrations.fastapi import setup_dishka
from dishka import make_async_container
from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.users import router as users_router
from app.routers.friends import router as friends_router

app = FastAPI(
    title="ErasMusic API",
    version="1.0.0",
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(friends_router)

container = make_async_container(AppProvider())
setup_dishka(container, app)
