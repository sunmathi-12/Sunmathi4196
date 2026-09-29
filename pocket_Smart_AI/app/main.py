from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import init_db
from app.routes.auth import router as auth_router
from app.routes.deps import get_current_user
from app.routes.planners import router as planner_router
from app.services.history import get_history


BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan
)


app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=False
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


app.mount(
    "/static",
    StaticFiles(
        directory=BASE_DIR / "static"
    ),
    name="static"
)


templates = Jinja2Templates(
    directory=BASE_DIR / "templates"
)

app.state.templates = templates


@app.get("/")
async def home(request: Request):

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request
        }
    )


@app.get("/dashboard")
async def dashboard(
    request: Request,
    user=Depends(get_current_user)
):

    history = get_history(
        user["username"],
        6
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "history": history
        }
    )


@app.get("/history")
async def history(
    request: Request,
    user=Depends(get_current_user)
):

    history_data = get_history(
        user["username"]
    )

    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "request": request,
            "user": user,
            "history": history_data
        }
    )


@app.get("/session-info")
async def session_info(
    request: Request,
    user=Depends(get_current_user)
):

    return {
        "user_id": user["id"],
        "username": user["username"],
        "logged_in": True
    }


@app.get("/session-data")
async def session_data(
    request: Request,
    user=Depends(get_current_user)
):

    return {
        "username": user["username"],
        "recent_history": get_history(
            user["username"],
            5
        )
    }


@app.get("/recommendations-details")
async def recommendation_details(
    request: Request,
    user=Depends(get_current_user)
):

    history = get_history(
        user["username"],
        1
    )

    if history:
        return history[0]["result"]

    return {
        "message": "No recommendations yet."
    }


@app.get("/startup")
async def startup_status():

    return {
        "status": "ok",
        "service": settings.app_name
    }


app.include_router(auth_router)
app.include_router(planner_router)