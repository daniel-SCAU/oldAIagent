import os
from typing import List
import httpx
from fastapi import FastAPI, Depends, Header, HTTPException, status
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_KEY: str
    LLM_ENDPOINT: str | None = None
    LLM_API_KEY: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

settings = Settings()
app = FastAPI(title="AI Suggestion Service", version="0.2.0")

async def require_api_key(x_api_key: str = Header(default="")):
    if not settings.API_KEY or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return True

class SuggestionIn(BaseModel):
    history: List[str]
    prompt: str

class SuggestionOut(BaseModel):
    text: str
    confidence: float

class SuggestionBundle(BaseModel):
    suggestions: List[SuggestionOut]

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/suggestions", response_model=SuggestionBundle, dependencies=[Depends(require_api_key)])
async def suggestions(body: SuggestionIn):
    if not settings.LLM_ENDPOINT or not settings.LLM_API_KEY:
        base = body.prompt.strip()
        opts = [
            SuggestionOut(text=base, confidence=0.55),
            SuggestionOut(text=f"Thanks for the message. {base}", confidence=0.45),
            SuggestionOut(text=f"I'll look into this and reply soon: {base}", confidence=0.35),
        ]
        return SuggestionBundle(suggestions=opts)

    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {"messages": [
        {"role": "system", "content": "Return two short, courteous reply options."},
        {"role": "user", "content": "\n".join(body.history[-10:] + [body.prompt])}
    ]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=3)) as client:
        r = await client.post(settings.LLM_ENDPOINT, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    texts = [c.get("text", "") for c in data.get("choices", [])][:2] or [body.prompt]
    out = [SuggestionOut(text=t, confidence=0.5 - i*0.1) for i, t in enumerate(texts)]
    return SuggestionBundle(suggestions=out)
