import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import analytics, auth, dashboard, feedback, payments, plans, settings, users, webhooks, whitelist
from bot.db.session import init_db
from bot.db.session import get_session
from bot.services.settings_store import seed_defaults

logger = logging.getLogger(__name__)

ADMIN_UI_DIR = Path(__file__).resolve().parent.parent / "admin-ui"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with get_session() as session:
        await seed_defaults(session)
    logger.info("API started")
    yield


app = FastAPI(title="vdown Admin API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(whitelist.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")

if ADMIN_UI_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=ADMIN_UI_DIR), name="assets")


@app.get("/")
async def admin_index():
    index = ADMIN_UI_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"message": "vdown Admin API", "docs": "/docs"}
