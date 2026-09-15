import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .api import router


app = FastAPI(title="Technologické předpisy", version="0.1.0")
secret = os.getenv("SPECS_SESSION_SECRET", "local-demo-session-secret-change-before-deploy")
if len(secret) < 32:
    raise RuntimeError("SPECS_SESSION_SECRET musí mít alespoň 32 znaků.")
@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/v1/"):
        if request.url.path != "/api/v1/auth/login" and request.session.get("user_id"):
            if request.headers.get("X-CSRF-Token") != request.session.get("csrf"):
                return JSONResponse(status_code=403, content={"detail": "Chybí ochranný token požadavku."})
    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key=secret, same_site="lax",
                   https_only=os.getenv("SPECS_COOKIE_SECURE", "false").lower() == "true")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(router)
