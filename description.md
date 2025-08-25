AI-beskedovervågnings-system med 2 api servere (FastAPI (android interface + myGPT interface) PostgreSQL, custom myGPT api).
Python baseret API der Integrerede en custom API til myGPT til behovsvurdering og svar-generering, PostgreSQL til historik og kontaktstyring.
Systemet holder øje med beskeder fra messenger, whatsapp, outlook, SMS, Aula m.m og laver automatisk klassificering, lagring og indexering af samtale tråde, kontakter etc.
Her fra kan man få opsumering på forskellige tråde, automatisk oprettet opgaver, og forslag til svar på beskeder baseret op historik og kontekst.

## Execution Plan

### Environment Setup

- Install Python, FastAPI, Flask, APScheduler, psycopg2, requests, and any other dependencies.
- Create `.env` or configuration file for API keys and database credentials.
- Verify PostgreSQL instance is running and accessible.

### Database Preparation

- Draft schema covering messages, conversation threads, contacts, and task summaries.
- Add classification and conversation ID fields.
- Create indexes for messages and contacts to improve lookup speed.
- Run migration scripts to create the database tables.

### FastAPI Service Development

- Implement endpoints: `/health`, `/webhook`, `/search`, `/conversations`.
- Add API-key authentication middleware.
- Launch background jobs for message categorization and summary processing.
- Integrate embedding/vector lookup for context search.

### Custom myGPT API (Flask)

- Build endpoints to send prompts, retrieve responses, acknowledge, store, and clear data.
- Enforce API-key validation on all routes.
- Maintain a thread-safe in-memory store of prompts and responses.
- (Optional) Integrate with external myGPT service for testing.

### Message Ingestion Modules

- Create adapters for Messenger, WhatsApp, Outlook, SMS, Aula, etc.
- Normalize each platform’s messages and forward to the FastAPI `/webhook` endpoint.
- Handle credentials, webhooks, and periodic polling logic for each platform.

### Classification & Indexing

- Implement message classification (question vs. statement or more refined categories).
- Store sender, platform, conversation ID, and timestamps.
- Ensure conversations and contacts are indexed for quick retrieval.

### Summarization & Task Automation

- Add endpoints to create summarization tasks tied to conversation IDs.
- Process and store summaries asynchronously.
- Auto-detect follow-up tasks within message content and persist them.

### Response Suggestions

- Generate reply suggestions using conversation history and embeddings via myGPT.
- Expose endpoints for clients (e.g., Android app) to request suggestions or submit replies.

### Client Interface Integration

- Develop or update an Android/UI client to interact with both APIs.
- Enable viewing conversation history, summaries, tasks, and response suggestions.

### Testing & Documentation

- Write pytest suites for authentication, background jobs, and message flows.
- Document setup steps, configuration, and usage in a README or guide.

These tasks should be executed in sequence or parallelized where feasible, ensuring each major component is tested and documented before moving to the next.

