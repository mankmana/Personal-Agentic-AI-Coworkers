# Personal Agentic AI Coworkers

A small career operating system for two career-focused AI coworkers:

1. **DailyTechUpgradeAgent** — the active coworker that watches the SRE, DevOps, and software support landscape, turns technical signals into a daily brief, and coaches you toward your next opportunity.
2. **NextLevelPersonalCoachForCareerLevel** — the planned second coworker for broader career planning and accountability.

The first coworker now has a working stdlib-only backend with seeded profile data, source ingestion, article summaries, challenges, assessment scoring, and a readiness report. The second coworker remains queued for a later phase.

## Run locally

The backend has no dependency install requirement.

```bash
python3 backend/server.py
```

Then open [http://localhost:4173](http://localhost:4173).

## What is included

- Overview dashboard with readiness, momentum, opportunities, and daily top-three brief.
- Personalized profile derived from career-relevant resume evidence; contact details are intentionally excluded from the repo.
- Two content lanes: general AI development and SRE / DevOps / software support.
- RSS/Atom ingestion with live-source support and deterministic extractive fallback summaries.
- Optional OpenAI Responses API adapter for model-backed summaries and evaluations when `OPENAI_API_KEY` is configured.
- Career lab with generated technical challenges, answer evaluation, and persisted readiness updates.
- JSON-backed local state for runs, answers, and progress; replace with Postgres in production.

## API surface

```text
GET  /api/health
GET  /api/profile
GET  /api/dashboard
GET  /api/articles?lane=general_ai_development|sre_devops_support|all
GET  /api/report
GET  /api/challenges/next?article_id=...
POST /api/scan
POST /api/assessments
```

Run a scan for both lanes:

```bash
curl -X POST http://localhost:4173/api/scan \
  -H 'Content-Type: application/json' \
  -d '{"lanes":["general_ai_development","sre_devops_support"]}'
```

The live RSS sources are configurable in `.env`; without network access or an API key, the service still returns the seeded demo articles and local fallback summaries.

## Next integration seam

The UI is ready to connect to a LangGraph or LangChain service. The natural graph nodes are:

`collect_sources → rank_relevance → summarize → assess_readiness → generate_challenge → recommend_plan`

Suggested production adapters are RSS/Atom feeds and official blogs first, then job boards, GitHub, arXiv, and OpenAI Responses API tools. Keep citations attached to every source summary and store progress events so the readiness report can evolve over time.

## Project structure

```text
.
├── backend/
│   ├── profile.json
│   └── server.py
├── index.html
├── styles.css
├── app.js
├── package.json
└── README.md
```
