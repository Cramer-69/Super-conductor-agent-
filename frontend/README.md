# Semantic Wall — frontend

A deliberately thin React (Vite) client proving the Semantic Wall API
contract (`../semantic_wall/api/main.py`) — chat, session-local history,
and the 30/5 check-in overlay. Not a polished product UI; see
`../semantic_wall/README.md` for the backend it talks to and the overall
project scope.

## Run locally

```bash
npm install
npm run dev
```

Defaults to `http://localhost:8090` for the backend; override with a
`VITE_SEMANTIC_WALL_URL` env var (or `.env.local`) if it's running
elsewhere.

## Build

```bash
npm run build
```
