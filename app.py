import os
import logging
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
import re
from secrets import compare_digest

import psycopg2
import psycopg2.pool
import requests
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from prompt_sender import myGPTAPI
from alembic import command
from alembic.config import Config

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

app = FastAPI(
    title="AI Message Monitoring API",
    version="0.2.0",
    description="Stores and searches messages across platforms.",
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------- DB pool ------------------
pool: Optional[psycopg2.pool.SimpleConnectionPool] = None
scheduler = BackgroundScheduler()


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


def run_migrations() -> None:
    """Apply database migrations using Alembic."""
    if pool is None:
        return
    cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    db_url = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    try:
        command.upgrade(cfg, "head")
        log.info("Migrations applied")
    except Exception as e:
        log.error("Migration failed: %s", e)


def init_db_schema() -> None:
    """Ensure required tables and columns exist."""
    if pool is None:
        return
    with db() as conn, conn.cursor() as cur:
        # add classification columns to Chat
        cur.execute(
            """
            ALTER TABLE IF EXISTS Chat
            ADD COLUMN IF NOT EXISTS category TEXT,
            ADD COLUMN IF NOT EXISTS intent TEXT,
            ADD COLUMN IF NOT EXISTS sentiment TEXT
            """
        )
        # create summary_tasks table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS summary_tasks (
                id SERIAL PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                summary TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        # create followup_tasks table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS followup_tasks (
                id SERIAL PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        # create contacts table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                info JSONB
            )
            """
        )


@app.on_event("startup")
def startup() -> None:
    init_db_pool()
    run_migrations()
    try:
        scheduler.start()
        scheduler.add_job(process_new_messages, IntervalTrigger(seconds=30))
        scheduler.add_job(process_summary_tasks, IntervalTrigger(seconds=60))
    except Exception as e:
        log.error("Scheduler start failed: %s", e)


@app.on_event("shutdown")
def shutdown() -> None:
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass

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
    if not compare_digest(x_api_key, API_KEY_EXPECTED):
        raise HTTPException(status_code=401, detail="Unauthorized")

# ------------- Models -------------------
class MessageIn(BaseModel):
    sender: str
    app: str
    message: str
    conversation_id: Optional[str] = None
    contact_id: Optional[int] = None

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


class ContactIn(BaseModel):
    name: str
    info: Optional[Dict[str, Any]] = None


class ContactRow(BaseModel):
    id: int
    name: str
    info: Optional[Dict[str, Any]]

class TaskCreate(BaseModel):
    conversation_id: str

class TaskRow(BaseModel):
    id: int
    conversation_id: str
    status: str
    summary: Optional[str]
    created_at: datetime


class SuggestionIn(BaseModel):
    conversation_id: str
    limit: int = 3


class SuggestionOut(BaseModel):
    suggestions: List[str]

# --------- Utilities ---------
def categorize_message(text: str) -> Dict[str, str]:
    """Determine intent and sentiment for a message.

    Attempts to use a configured myGPT instance if available. The model is
    prompted to return a JSON object with ``intent`` (``question``, ``task`` or
    ``statement``) and ``sentiment`` (``positive``, ``negative`` or ``neutral``).
    If the model call fails or is not configured, a simple heuristic fallback is
    used instead.
    """

    api_url = os.getenv("MYGPT_API_URL")
    api_key = os.getenv("MYGPT_API_KEY")
    if api_url and api_key:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = (
            "Classify the following message. Respond with JSON containing keys "
            "'intent' (question/task/statement) and 'sentiment' (positive/negative/neutral).\n"
            f"Message: {text}"
        )
        try:
            resp = requests.post(api_url, headers=headers, json={"prompt": prompt}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            # Some myGPT deployments may return the JSON directly or embed it in 'response'
            if isinstance(data, dict) and "intent" in data:
                intent = data.get("intent")
                sentiment = data.get("sentiment")
            else:
                resp_text = data.get("response") or data.get("answer")
                intent = sentiment = None
                if resp_text:
                    try:
                        parsed = json.loads(resp_text)
                        intent = parsed.get("intent")
                        sentiment = parsed.get("sentiment")
                    except Exception:
                        pass
            if intent and sentiment:
                return {"intent": intent, "sentiment": sentiment}
        except Exception as e:
            log.error("categorize_message myGPT failed: %s", e)

    text = text or ""
    lower = text.lower()
    intent = "statement"
    if "?" in text:
        intent = "question"
    elif any(k in lower for k in ["please", "can you", "could you", "todo", "kindly", "follow up"]):
        intent = "task"

    sentiment = "neutral"
    positive_words = ["good", "great", "love", "like", "excellent", "happy", "awesome", "fantastic"]
    negative_words = ["bad", "terrible", "hate", "dislike", "awful", "sad", "angry"]
    if any(w in lower for w in positive_words):
        sentiment = "positive"
    elif any(w in lower for w in negative_words):
        sentiment = "negative"

    return {"intent": intent, "sentiment": sentiment}


def detect_followup_tasks(text: str) -> List[str]:
    """Extract possible follow-up tasks from a message.

    A very lightweight heuristic is used: any sentence containing
    keywords like "todo", "please", "can you" or "follow up" is
    treated as a task.
    """
    tasks: List[str] = []
    if not text:
        return tasks
    for sentence in re.split(r"[\n\.!?]+", text):
        s = sentence.strip()
        if not s:
            continue
        lower = s.lower()
        if any(k in lower for k in ["todo", "please", "can you", "could you", "follow up", "follow-up", "remind", "need to"]):
            tasks.append(s)
    return tasks


def summarize_messages(messages: List[str]) -> str:
    if not messages:
        return ""
    prompt = "Summarize the following conversation:\n" + "\n".join(messages)
    try:
        api = myGPTAPI()
        result = api.generate_test_response(prompt)
        summary = result.get("response") or result.get("summary") or result.get("answer")
        if summary:
            return summary.strip()
    except Exception as e:
        log.error("Summary generation failed: %s", e)
    if len(messages) == 1:
        return messages[0]
    return f"{messages[0]} ... {messages[-1]}"


def summarize_conversation(conversation_id: str) -> str:
    sql = """
        SELECT message FROM Chat
        WHERE conversation_id = %s
        ORDER BY created_at ASC
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (conversation_id,))
        rows = cur.fetchall()
    msgs = [r[0] for r in rows if r and r[0]]
    return summarize_messages(msgs)


def process_new_messages() -> None:
    """Assign categories to uncategorized messages."""
    sql_select = (
        "SELECT id, message FROM Chat WHERE intent IS NULL OR sentiment IS NULL LIMIT 50"
    )
    sql_update = "UPDATE Chat SET intent=%s, sentiment=%s, category=%s WHERE id=%s"
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql_select)
        rows = cur.fetchall()
        for mid, msg in rows:
            meta = categorize_message(msg or "")
            cur.execute(sql_update, (meta["intent"], meta["sentiment"], meta["intent"], mid))


def process_summary_tasks() -> None:
    """Process pending summary tasks."""
    sql_pending = "SELECT id, conversation_id FROM summary_tasks WHERE status = 'pending'"
    sql_update = "UPDATE summary_tasks SET summary=%s, status='completed' WHERE id=%s"
    sql_fail = "UPDATE summary_tasks SET status='failed' WHERE id=%s"
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql_pending)
        tasks = cur.fetchall()
        for tid, cid in tasks:
            try:
                summary = summarize_conversation(cid)
                cur.execute(sql_update, (summary, tid))
            except Exception as e:
                log.error("Failed to summarize %s: %s", cid, e)
                cur.execute(sql_fail, (tid,))

# ------------- Endpoints ----------------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/messages", response_model=MessageOut, dependencies=[Depends(require_api_key)])
def create_message(msg: MessageIn):
    with db() as conn:
        with conn.cursor() as cur:
            if msg.conversation_id:
                if msg.contact_id is not None:
                    cur.execute(
                        """
                        INSERT INTO Chat (sender, app, message, conversation_id, contact_id)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, conversation_id, created_at
                        """,
                        (msg.sender, msg.app, msg.message, msg.conversation_id, msg.contact_id),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO Chat (sender, app, message, conversation_id)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, conversation_id, created_at
                        """,
                        (msg.sender, msg.app, msg.message, msg.conversation_id),
                    )
            else:
                if msg.contact_id is not None:
                    cur.execute(
                        """
                        INSERT INTO Chat (sender, app, message, contact_id)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, conversation_id, created_at
                        """,
                        (msg.sender, msg.app, msg.message, msg.contact_id),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO Chat (sender, app, message)
                        VALUES (%s, %s, %s)
                        RETURNING id, conversation_id, created_at
                        """,
                        (msg.sender, msg.app, msg.message),
                    )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Insert failed")
            _id, cid, created_at = row
            tasks = detect_followup_tasks(msg.message)
            if tasks:
                sql_task = "INSERT INTO followup_tasks (conversation_id, task) VALUES (%s, %s)"
                for t in tasks:
                    cur.execute(sql_task, (cid, t))
            return {"id": _id, "conversation_id": str(cid), "created_at": created_at}


@app.post("/webhook", response_model=MessageOut, dependencies=[Depends(require_api_key)])
def webhook_ingest(msg: MessageIn):
    """Accept normalized message payloads and store via create_message."""
    return create_message(msg)


@app.post("/suggestions", response_model=SuggestionOut, dependencies=[Depends(require_api_key)])
def generate_suggestions(req: SuggestionIn):
    """Generate reply suggestions for a conversation using myGPT."""
    sql = """
        SELECT sender, message FROM Chat
        WHERE conversation_id = %s
        ORDER BY created_at ASC
        LIMIT 50
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (req.conversation_id,))
        rows = cur.fetchall()
    history = "\n".join(f"{s}: {m}" for s, m in rows if m)
    prompt = (
        f"Conversation:\n{history}\n"
        f"Provide {req.limit} possible replies."
    )
    api = myGPTAPI()
    try:
        result = api.generate_test_response(prompt)
        text = result.get("response", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"myGPT error: {e}")
    suggestions = [s.strip() for s in text.splitlines() if s.strip()][: req.limit]
    return {"suggestions": suggestions}

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


@app.post("/contacts", response_model=ContactRow, dependencies=[Depends(require_api_key)])
def create_contact(contact: ContactIn):
    sql = """
        INSERT INTO contacts (name, info)
        VALUES (%s, %s)
        RETURNING id, name, info
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (contact.name, json.dumps(contact.info) if contact.info else None))
        row = cur.fetchone()
        return {"id": row[0], "name": row[1], "info": row[2]}


@app.get("/contacts", response_model=List[ContactRow], dependencies=[Depends(require_api_key)])
def list_contacts():
    sql = "SELECT id, name, info FROM contacts ORDER BY id"
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        return [{"id": r[0], "name": r[1], "info": r[2]} for r in rows]

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


# --------- Task Endpoints ---------
@app.post("/tasks", response_model=TaskRow, dependencies=[Depends(require_api_key)])
def create_task(task: TaskCreate):
    sql = """
        INSERT INTO summary_tasks (conversation_id)
        VALUES (%s)
        RETURNING id, conversation_id, status, summary, created_at
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (task.conversation_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Insert failed")
        return {
            "id": row[0],
            "conversation_id": row[1],
            "status": row[2],
            "summary": row[3],
            "created_at": row[4],
        }


@app.get("/tasks", response_model=List[TaskRow], dependencies=[Depends(require_api_key)])
def list_tasks():
    sql = """
        SELECT id, conversation_id, status, summary, created_at
        FROM summary_tasks
        ORDER BY created_at DESC
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "conversation_id": r[1],
                "status": r[2],
                "summary": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]


@app.get("/tasks/{task_id}", response_model=TaskRow, dependencies=[Depends(require_api_key)])
def get_task(task_id: int):
    sql = """
        SELECT id, conversation_id, status, summary, created_at
        FROM summary_tasks
        WHERE id = %s
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (task_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return {
            "id": row[0],
            "conversation_id": row[1],
            "status": row[2],
            "summary": row[3],
            "created_at": row[4],
        }


@app.delete("/tasks/{task_id}", dependencies=[Depends(require_api_key)])
def delete_task(task_id: int):
    sql = "DELETE FROM summary_tasks WHERE id = %s"
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, (task_id,))
    return {"ok": True}

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
    log.info("Starting API on 0.0.0.0:8000")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
