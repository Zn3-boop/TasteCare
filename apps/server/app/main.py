import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Force UTF-8 encoding
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

if hasattr(sys.stdout, 'reconfigure') and (sys.stdout.encoding or '').lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure') and (sys.stderr.encoding or '').lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# .env is loaded centrally by app/core/config.py (pydantic-settings Settings with
# env_file pointing to apps/server/.env); no need to call load_dotenv again here.

# Web demo (apps/web) focus: import only the 6 routers used by the web demo.
# Desktop routers (automation / voice / desktop / provider / browser / agent …)
# are intentionally not imported; their files no longer expose routes.
from app.api import ablation, chat, community, health, memory, qloo, tastecare, tools
from app.utils.response_cleaner import clean_fastapi_response_body


# ========== Lifespan replaces the deprecated on_event("startup") ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.services.rag.store import DualIndexStore
        print("RAG store available")
    except Exception as e:
        print(f"Warning: RAG store init skipped: {e}")
    yield


app = FastAPI(
    title="AI Desktop Agent API",
    version="0.1.0",
    lifespan=lifespan,
)


# ========== CORS: supports the CORS_ALLOW_ALL switch ==========
# Deployment-critical config lives in app/core/config.py (pydantic-settings), parsed once at startup.
from app.core.config import get_settings

_settings = get_settings(cache=True)
_allowed_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins if not _settings.cors_allow_all else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Global middleware: UTF-8 + exception safety ==========
@app.middleware("http")
async def ensure_utf8(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        # Never leak internal error details to clients; return a generic message.
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again later or contact the administrator."},
            media_type='application/json; charset=utf-8',
        )

    content_type = response.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
    elif 'charset=' not in content_type and content_type.startswith('text/'):
        response.headers['Content-Type'] = f'{content_type}; charset=utf-8'
    return response


# ========== Global middleware: response cleaning ==========
@app.middleware("http")
async def clean_response_middleware(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get('Content-Type', '')

    if 'application/json' not in content_type:
        return response

    body = b''
    async for chunk in response.body_iterator:
        body += chunk

    cleaned_body = clean_fastapi_response_body(body)
    headers = dict(response.headers)
    headers.pop('content-length', None)

    import json
    return JSONResponse(
        content=json.loads(cleaned_body.decode('utf-8')),
        status_code=response.status_code,
        headers=headers,
        media_type='application/json; charset=utf-8',
    )

# Simple route smoke tests
@app.get("/")
async def root():
    return {"status": "ok", "name": "AI Desktop Agent API"}

@app.get("/health")
async def Health_check():
    return {"status": "healthy"}

# ========== Web demo routes (business routers under /api/v1; / and /health are liveness paths, no version) ==========
API_V1_PREFIX = "/api/v1"
app.include_router(health.router)
app.include_router(chat.router, prefix=API_V1_PREFIX)
app.include_router(tools.router, prefix=API_V1_PREFIX)
app.include_router(qloo.router, prefix=API_V1_PREFIX)
app.include_router(tastecare.router, prefix=API_V1_PREFIX)
app.include_router(ablation.router, prefix=API_V1_PREFIX)
app.include_router(memory.router, prefix=API_V1_PREFIX)
app.include_router(community.router, prefix=API_V1_PREFIX)