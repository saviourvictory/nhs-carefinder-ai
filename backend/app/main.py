from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.schemas import SearchRequest, SearchResponse
from app.services.assistant import chat
from app.services.directory import search_directory

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(title="NHS CareFinder AI", version="0.2.0")
app.state.limiter = limiter
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")],
                   allow_credentials=False, allow_methods=["GET","POST"], allow_headers=["Content-Type"])

@app.middleware("http")
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update({
        "X-Content-Type-Options":"nosniff", "X-Frame-Options":"DENY",
        "Referrer-Policy":"no-referrer", "Permissions-Policy":"camera=(), microphone=(), geolocation=()",
        "Cache-Control":"no-store",
    })
    return response

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail":"Too many requests"})

@app.get("/health")
async def health():
    return {"status":"ok", "demo_mode":settings.demo_mode, "live_directory_configured":bool(settings.nhs_api_key)}

@app.post("/api/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search(request: Request, payload: SearchRequest):
    try:
        providers = await search_directory(payload.service, payload.postcode, payload.limit, payload.radius_miles)
    except httpx_error_types() as exc:
        raise HTTPException(status_code=502, detail="NHS directory is temporarily unavailable") from exc
    notice = ("Synthetic demonstration results only; do not contact these fictional providers."
              if settings.demo_mode or not settings.nhs_api_key else
              "Directory listing does not confirm appointment availability or clinical suitability.")
    return SearchResponse(results=providers, notice=notice)

def httpx_error_types():
    import httpx
    return (httpx.HTTPError,)

@app.post("/api/chat")
@limiter.limit("8/minute")
async def assistant(request: Request, body: dict):
    question = body.get("question")
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1200:
        raise HTTPException(status_code=422, detail="Question must be 1–1200 characters")
    return await chat(question.strip())
