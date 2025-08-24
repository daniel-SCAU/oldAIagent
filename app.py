import os
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

import psycopg2
import psycopg2.pool
import requests
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------- Config ----------------
DEBUG = os.getenv("DEBUG", "1") == "1"
API_KEY_EXPECTED = os.getenv("API_KEY", "dev-api-key")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "54322")),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
    "dbname": os.getenv("DB_NAME", "postgres"),
}

EMBEDDING_ENDPOINT = os.getenv("OLLAMA_EMBEDDINGS_URL", "http://127.0.0.1:11434/api/embeddings")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large:335m")
SUPABASE_REST_URL = os.getenv("SUPABASE_REST_URL", "http://127.0.0.1:54321")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("api")

# ------------- DB pool ------------------
pool: Optional[psycopg2.pool.SimpleConnectionPool] = None


def init_db_pool() -> None:
    """Initialize the global DB connection pool.

    If the database is unavailable, the application will continue running
    without a pool and database-dependent endpoints will return an error
    when accessed.
    """
    global pool
    try:
        pool = psycopg2.pool.SimpleConnectionPool(minconn=1, maxconn=10, **DB_CONFIG)
        log.info("DB pool ready")
    except Exception as e:
        pool = None
        log.error("DB pool init failed: %s", e)


@app.on_event("startup")
def startup_db_pool() -> None:
    init_db_pool()

@contextmanager
def db() -> psycopg2.extensions.connection:
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    conn = None
    try:
        conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            pool.putconn(conn)

# ------------- Auth ---------------------
def require_api_key(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY_EXPECTED:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ------------- Models -------------------
class MessageIn(BaseModel):
    sender: str
    app: str
    message: str
    conversation_id: Optional[str] = None

class MessageOut(BaseModel):
    id: int
    conversation_id: str
    created_at: datetime

class MessageRow(BaseModel):
    id: int
    conversation_id: Optional[str]
    sender: Optional[str]
    app: Optional[str]
    message: Optional[str]
    created_at: datetime
    contact_id: Optional[str] = None
    message_type: Optional[str] = None
    thread_key: Optional[str] = None

# ------------- App ----------------------
app = FastAPI(
    title="AI Message Monitoring API",
    version="0.2.0",
    description="Stores and searches messages across platforms."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ------------- Endpoints ----------------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/messages", response_model=MessageOut, dependencies=[Depends(require_api_key)])
def create_message(msg: MessageIn):
    sql_with_conv = """
        INSERT INTO Chat (sender, app, message, conversation_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id, conversation_id, created_at
    """
    sql_new_conv = """
        INSERT INTO Chat (sender, app, message)
        VALUES (%s, %s, %s)
        RETURNING id, conversation_id, created_at
    """
    with db() as conn:
        with conn.cursor() as cur:
            if msg.conversation_id:
                cur.execute(sql_with_conv, (msg.sender, msg.app, msg.message, msg.conversation_id))
            else:
                cur.execute(sql_new_conv, (msg.sender, msg.app, msg.message))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Insert failed")
            _id, cid, created_at = row
            return {"id": _id, "conversation_id": str(cid), "created_at": created_at}

@app.get("/search", response_model=List[MessageRow], dependencies=[Depends(require_api_key)])
def search_messages(q: str = Query(..., min_length=1), limit: int = Query(50, ge=1, le=500)):
    sql = """
        SELECT id, conversation_id, sender, app, message, created_at,
               contact_id, message_type, thread_key
        FROM Chat
        WHERE message ILIKE %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (f"%{q}%", limit))
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "conversation_id": str(r[1]) if r[1] is not None else None,
                "sender": r[2],
                "app": r[3],
                "message": r[4],
                "created_at": r[5],
                "contact_id": str(r[6]) if r[6] is not None else None,
                "message_type": r[7],
                "thread_key": r[8],
            })
        return out

@app.get("/conversations/{conversation_id}/messages",
         response_model=List[MessageRow],
         dependencies=[Depends(require_api_key)])
def list_conversation_messages(conversation_id: str, limit: int = Query(200, ge=1, le=1000)):
    sql = """
        SELECT id, conversation_id, sender, app, message, created_at,
               contact_id, message_type, thread_key
        FROM Chat
        WHERE conversation_id = %s
        ORDER BY created_at ASC
        LIMIT %s
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (conversation_id, limit))
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "conversation_id": str(r[1]) if r[1] is not None else None,
                "sender": r[2],
                "app": r[3],
                "message": r[4],
                "created_at": r[5],
                "contact_id": str(r[6]) if r[6] is not None else None,
                "message_type": r[7],
                "thread_key": r[8],
            })
        return out

# ---------- Optional: context RPC (kept) ----------
def _embedding(text: str):
    try:
        resp = requests.post(EMBEDDING_ENDPOINT, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=20)
        resp.raise_for_status()
        return resp.json().get("embedding")
    except Exception as e:
        log.error("Embedding error: %s", e)
        return None

@app.post("/context", dependencies=[Depends(require_api_key)])
def match_context(text: str, match_threshold: float = 0.75, match_count: int = 5) -> Dict[str, Any]:
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Vector matching not configured")
    emb = _embedding(text)
    if not emb:
        raise HTTPException(status_code=500, detail="Embedding failed")
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"query_embedding": emb, "match_threshold": match_threshold, "match_count": match_count}
    try:
        r = requests.post(f"{SUPABASE_REST_URL}/rest/v1/rpc/match_documents", headers=headers, json=payload, timeout=25)
        r.raise_for_status()
        return {"context": r.json()}
    except Exception as e:
        log.error("Context RPC failed: %s", e)
        raise HTTPException(status_code=500, detail="Context retrieval failed")

if __name__ == "__main__":
    import uvicorn
    log.info("Starting API on 0.0.0.0:8001")
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
