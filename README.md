# StockPulse

Order + inventory management with live updates — a small system deliberately
scoped to cover: REST auth, async job processing, a cross-language event
boundary, websocket delivery, and static serving behind one reverse proxy.

## Architecture

- **Django + DRF** — orders and stock (source of truth), JWT auth
- **Celery + Redis** — async order processing, retries, dead-letter handling
- **Fastify (Node)** — websocket delivery, Redis pub/sub subscriber
- **React (Vite)** — order dashboard, live feed, live stock counter
- **Nginx** — TLS, static serving, reverse proxy (`/api` → Django, `/ws` → Node)
- **Postgres**

Flow: order placed → Django persists it → Celery processes it async →
publishes to Redis → Fastify picks it up → pushes to connected clients over
websocket → React updates without a refresh.

## Local development

Requires Docker + Docker Compose.

\`\`\`bash
cp .env.example .env
docker compose up --build
\`\`\`

- Frontend: http://localhost:5173
- API: http://localhost:8000/api
- Admin: http://localhost:8000/admin

## Services

| Service   | Path         | Purpose                          |
|-----------|--------------|-----------------------------------|
| backend   | `/backend`   | Django + DRF + Celery worker      |
| ws-service| `/ws-service`| Fastify websocket server          |
| frontend  | `/frontend`  | React dashboard                   |

## Deployment

Production Compose file + Nginx config + Certbot setup live in `/nginx` and
`docker-compose.prod.yml`. See deployment notes in `/docs` (WIP).

## Status

Work in progress — build log and design notes: (link to blog post, once written)

## License

MIT