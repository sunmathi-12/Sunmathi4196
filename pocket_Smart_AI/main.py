import os, json, sqlite3, hashlib, secrets, datetime as dt
from contextlib import asynccontextmanager
import jwt
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import gemini_utils as ai

SECRET = os.getenv("SECRET_KEY", "dev-secret-change-me")
DB = os.getenv("DB_PATH", "pocketsmart.db")
B = ("budget", "Total budget (INR)", "number", [])
FORMS = {
    "home": ("Home Interior Planner", [B, ("rooms", "Rooms (e.g. Living Room, Kitchen)", "text", []),
             ("lights", "Lights", "number", []), ("fans", "Ceiling fans", "number", []),
             ("dining_tables", "Dining tables", "number", []),
             ("style", "Style", "select", ["Modern", "Minimal", "Traditional", "Scandinavian"])]),
    "party": ("Party Planner", [B, ("guests", "Guests", "number", []),
              ("event_type", "Event type", "select", ["Birthday", "Corporate", "Wedding", "Get-together"]),
              ("venue", "Venue details", "text", [])]),
    "jewelry": ("Jewelry Planner", [B, ("occasion", "Occasion", "select", ["Wedding", "Festival", "Party", "Office"]),
                ("style", "Style", "select", ["Traditional", "Modern", "Minimal", "Statement"]),
                ("outfit_image", "Outfit photo (optional)", "file", [])]),
}


def q(sql, args=()):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(sql, args).fetchall()
        c.commit()
        return rows
    finally:
        c.close()


@asynccontextmanager
async def lifespan(app):  # startup: create tables
    q("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)")
    q("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, user_id INTEGER, category TEXT, budget REAL, result TEXT, created TEXT)")
    yield


app = FastAPI(title="PocketSmart AI", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class NeedLogin(Exception):
    pass


@app.exception_handler(NeedLogin)
async def need_login(request, exc):
    return RedirectResponse("/login", 303)


def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 100_000).hex()


def make_token(u):
    return jwt.encode({"sub": u, "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)}, SECRET, algorithm="HS256")


def get_user(request: Request):
    tok = request.cookies.get("token") or request.headers.get("authorization", "").removeprefix("Bearer ")
    try:
        name = jwt.decode(tok, SECRET, algorithms=["HS256"])["sub"]
    except Exception:
        return None
    rows = q("SELECT * FROM users WHERE username=?", (name,))
    return rows[0] if rows else None


def current_user(request: Request):
    u = get_user(request)
    if not u:
        raise NeedLogin()
    return u


def page(request, name, **ctx):
    return templates.TemplateResponse(request, name, {"user": get_user(request), **ctx})


def signed_in(username):
    r = RedirectResponse("/dashboard", 303)
    r.set_cookie("token", make_token(username), httponly=True, samesite="lax", max_age=28800)
    return r


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return page(request, "index.html", forms=FORMS)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return page(request, "auth.html", mode="register", error="")


@app.post("/register")
async def register(request: Request):
    f = await request.form()
    u, p = str(f.get("username", "")).strip(), str(f.get("password", ""))
    if len(u) < 3 or len(p) < 6:
        return page(request, "auth.html", mode="register", error="Username needs 3+ characters and password 6+.")
    if q("SELECT 1 FROM users WHERE username=?", (u,)):
        return page(request, "auth.html", mode="register", error="That username is taken.")
    q("INSERT INTO users(username,password) VALUES(?,?)", (u, hash_pw(p)))
    return signed_in(u)


def verify(u, p):
    rows = q("SELECT * FROM users WHERE username=?", (u,))
    ok = rows and secrets.compare_digest(hash_pw(p, rows[0]["password"].split("$")[0]), rows[0]["password"])
    return bool(ok)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return page(request, "auth.html", mode="login", error="")


@app.post("/login")
async def login(request: Request):
    f = await request.form()
    u = str(f.get("username", "")).strip()
    if not verify(u, str(f.get("password", ""))):
        return page(request, "auth.html", mode="login", error="Wrong username or password.")
    return signed_in(u)


@app.post("/token")
async def token(request: Request):
    f = await request.form()
    u = str(f.get("username", ""))
    if not verify(u, str(f.get("password", ""))):
        raise HTTPException(401, "Wrong username or password")
    return {"access_token": make_token(u), "token_type": "bearer"}


@app.get("/logout")
async def logout():
    r = RedirectResponse("/login", 303)
    r.delete_cookie("token")
    return r


def planner(request, kind, vals=None, result=None, error=""):
    title, fields = FORMS[kind]
    return page(request, "planner.html", kind=kind, title=title, fields=fields, vals=vals or {}, result=result, error=error)


@app.get("/planner/{kind}", response_class=HTMLResponse)
async def planner_page(kind: str, request: Request, user=Depends(current_user)):
    if kind not in FORMS:
        raise HTTPException(404)
    return planner(request, kind)


async def handle(kind, request):
    form = await request.form()
    vals = {k: v.strip() for k, v in form.items() if isinstance(v, str)}
    try:
        budget = float(vals.get("budget", ""))
    except ValueError:
        budget = 0
    if budget <= 0:
        return planner(request, kind, vals, error="Enter a budget greater than 0.")
    image, up = None, form.get("outfit_image")
    if up is not None and not isinstance(up, str) and up.filename:
        data = await up.read()
        if len(data) > 4_000_000 or not (up.content_type or "").startswith("image/"):
            return planner(request, kind, vals, error="Upload an image under 4 MB.")
        image = (data, up.content_type)
    result = ai.recommend(kind, budget, vals, image)
    q("INSERT INTO history(user_id,category,budget,result,created) VALUES(?,?,?,?,?)",
      (get_user(request)["id"], kind, budget, json.dumps(result), dt.datetime.now().strftime("%d %b %Y, %H:%M")))
    return planner(request, kind, vals, result)


def make_endpoint(kind):
    async def endpoint(request: Request, user=Depends(current_user)):
        return await handle(kind, request)
    return endpoint


for _k in FORMS:  # /generate-home, /generate-party, /generate-jewelry
    app.add_api_route(f"/generate-{_k}", make_endpoint(_k), methods=["POST"], response_class=HTMLResponse)


def rows_for(user, limit):
    out = []
    for r in q("SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?", (user["id"], limit)):
        d = dict(r)
        d["result"] = json.loads(d["result"])
        out.append(d)
    return out


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(current_user)):
    return page(request, "history.html", title="Dashboard", rows=rows_for(user, 3))


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request, user=Depends(current_user)):
    return page(request, "history.html", title="Recommendation history", rows=rows_for(user, 100))


@app.get("/recommendations-details")
async def details(id: int, user=Depends(current_user)):
    rows = q("SELECT * FROM history WHERE id=? AND user_id=?", (id, user["id"]))
    if not rows:
        raise HTTPException(404)
    return {**dict(rows[0]), "result": json.loads(rows[0]["result"])}


@app.get("/session-info")
async def session_info(user=Depends(current_user)):
    return {"user_id": user["id"], "username": user["username"], "logged_in": True}


@app.get("/session-data")
async def session_data(user=Depends(current_user)):
    rows = rows_for(user, 100)
    return {"total_queries": len(rows), "recent_categories": [r["category"] for r in rows[:5]]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
