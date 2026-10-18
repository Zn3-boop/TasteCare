import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 强制 UTF-8 编码
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

if hasattr(sys.stdout, 'reconfigure') and (sys.stdout.encoding or '').lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure') and (sys.stderr.encoding or '').lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# .env 已由 app/core/config.py 的 pydantic-settings Settings（env_file 指向
# apps/server/.env）统一加载，无需在此重复 load_dotenv。

# Web demo（apps/web）专注：仅 import web demo 用到的 6 个 router。
# 桌面端 router(automation / voice / desktop / provider / browser / agent 等)
# 已全部清理，不再 import；相关文件不再暴露路由。
from app.api import ablation, chat, community, health, memory, qloo, tastecare, tools
from app.utils.response_cleaner import clean_fastapi_response_body


# ========== 使用 lifespan 替代废弃的 on_event("startup") ==========
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


# ========== CORS 配置：支持 CORS_ALLOW_ALL 开关 ==========
# 部署关键配置集中在 app/core/config.py（pydantic-settings），启动时解析一次。
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


# ========== 全局中间件：确保 UTF-8 + 异常安全处理 ==========
@app.middleware("http")
async def ensure_utf8(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        # 不暴露内部错误详情给客户端，只返回通用错误
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请稍后再试或联系管理员。"},
            media_type='application/json; charset=utf-8',
        )

    content_type = response.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
    elif 'charset=' not in content_type and content_type.startswith('text/'):
        response.headers['Content-Type'] = f'{content_type}; charset=utf-8'
    return response


# ========== 全局中间件：清洗响应 ==========
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

# 简单路由测试
@app.get("/")
async def root():
    return {"status": "ok", "name": "AI Desktop Agent API"}

@app.get("/health")
async def Health_check():
    return {"status": "healthy"}

# ========== Web demo 路由注册（业务路由统一 /api/v1 前缀；/ 与 /health 为探活路径，不加版本） ==========
API_V1_PREFIX = "/api/v1"
app.include_router(health.router)
app.include_router(chat.router, prefix=API_V1_PREFIX)
app.include_router(tools.router, prefix=API_V1_PREFIX)
app.include_router(qloo.router, prefix=API_V1_PREFIX)
app.include_router(tastecare.router, prefix=API_V1_PREFIX)
app.include_router(ablation.router, prefix=API_V1_PREFIX)
app.include_router(memory.router, prefix=API_V1_PREFIX)
app.include_router(community.router, prefix=API_V1_PREFIX)