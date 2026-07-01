# Semantic Wall — Phase 1 MVP

The shared, persistent-memory + single-agent backend from the
`SemanticAIWallBlueprint.pdf` product plan — built first, as
infrastructure, so every other client app (a Claude-only app, a
multi-provider app, the iOS scaffold in `../ios/ConductorApp/`) can
connect to one backend instead of re-implementing memory/embeddings/agent
orchestration itself.

**This is Phase 1 only** — matching the blueprint's own phased build plan.
Implemented: one agent (`strategist`, configurable), persistent vector
memory, and the 30/5 check-in loop. **Explicitly not implemented yet**
(the blueprint's own Phase 2+): the 20-agent farm, cost/quality model
routing, the lie-detection classifier, Stripe billing, data licensing,
and enterprise multi-tenant white-labeling. None of that is stubbed or
faked — it's just future work.

This is architecturally independent from the rest of this repo (its own
datastore, its own API, its own deployment) — nothing in `conductor/`,
`connectors/`, or `api/` was touched to build this.

## Architecture

```
semantic_wall/
  config.py           Settings (Supabase + LLM provider keys, all optional/gated)
  db/
    schema.sql        pgvector extension, memories + checkins tables, RLS, match_memories() RPC
    supabase_client.py  gated client — is_configured() before any use
  memory/
    embeddings.py     OpenAI text-embedding-3-large, disk-cached
    store.py          write_memory / search_memories / mark_session_outcome
  agent/
    core.py           single agent, memory-injected, reuses ../conductor/tool_loop.py
  checkin/
    engine.py         active-usage timer + 5-question check-in + outcome write-back
  api/
    main.py           FastAPI: /api/chat, /api/checkin, /api/checkin/status, /health
```

Why `semantic_wall.*`-qualified imports rather than bare ones: this
service lives inside the same repo/CI as the sibling Conductor app, which
already has top-level `config/` and `api/` packages of its own. Bare
imports collide the moment both test suites run in the same `pytest`
process (Python caches modules by name, not by which package actually
satisfied the import) — qualifying everything under `semantic_wall.`
avoids that entirely. See `../conductor/tool_loop.py` and
`../connectors/registry.py` for the same qualified-import convention
already used elsewhere in this repo.

## Local setup

1. **Supabase** (optional but needed for memory to actually persist):
   create a project at [supabase.com](https://supabase.com), open its SQL
   editor, and run `db/schema.sql`. Copy the project URL and a service-role
   key into `SUPABASE_URL`/`SUPABASE_KEY`.
2. **LLM provider**: set at least one of `ANTHROPIC_API_KEY`,
   `XAI_API_KEY`, `OPENAI_API_KEY` (embeddings always use OpenAI
   regardless of which one answers chat — `OPENAI_API_KEY` is required if
   Supabase is configured, even if a different provider answers).
3. Copy `.env.example` to `.env` and fill in the above.
4. From the **repo root** (imports are `semantic_wall.*`-qualified):
   ```bash
   pip install -r semantic_wall/requirements.txt
   python -m uvicorn semantic_wall.api.main:app --reload --port 8090
   ```
5. Frontend: `cd frontend && npm install && npm run dev` (defaults to
   pointing at `http://localhost:8090`; override with
   `VITE_SEMANTIC_WALL_URL`).

## Testing

Tests live in the repo's shared `../tests/semantic_wall/` (not nested
inside this directory) for the same reason imports are qualified — so
`pytest` from the repo root picks up both this service's tests and the
sibling app's tests in one run with no path conflicts:

```bash
pytest tests/semantic_wall/   # from the repo root
```

All tests mock Supabase/LLM clients — no live network calls, no
credentials required to run them.

## Deployment

Build context must be the **repo root** (not this directory) since
imports are `semantic_wall.*`-qualified. `gcloud run deploy --source`
only looks for a Dockerfile at the root of its source directory, so it
can't be pointed at `semantic_wall/Dockerfile` directly with repo-root
context — build the image explicitly instead, from the repo root:

```bash
docker build -f semantic_wall/Dockerfile -t semantic-wall .
docker push <your-registry>/semantic-wall
gcloud run deploy semantic-wall --image <your-registry>/semantic-wall \
  --set-env-vars SUPABASE_URL=...,ANTHROPIC_API_KEY=...
```

(Use `--set-secrets` instead of `--set-env-vars` for real deployments —
see the sibling app's own `../README.md` Deploy section for the Secret
Manager pattern already established in this repo.)

## Known Phase 1 limitations

- **Check-in activity tracking is in-process memory** (`checkin/engine.py`),
  not persisted. Fine for a single instance; won't survive a restart or
  work correctly if this service scales to multiple Cloud Run instances.
  Swap it for a Redis/Postgres-backed store before that happens.
- **No multi-agent routing** — one agent (`strategist` by default,
  configurable per request), not the blueprint's 20-agent farm.
- **No lie-detection / anomaly flagging** on check-in responses — that's
  explicitly Phase 3 in the blueprint's own build plan.
