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

- Overview dashboard with readiness, momentum, and a daily top-three technical brief. Relevant opportunities are intentionally reserved for `NextLevelPersonalCoachForCareerLevel` and are not part of this coworker.
- Personalized profile derived from career-relevant resume evidence; contact details are intentionally excluded from the repo.
- Two content lanes: general AI development and SRE / DevOps / software support.
- Source-grounded RSS/Atom ingestion. Every article returned by the backend has a source URL and is summarized from fetched feed or article-page text; the service does not serve seeded article cards.
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

The live source lanes are configurable in `.env`; start from `config/.env.example`. The general lane currently watches official OpenAI News and Google AI feeds. The domain lane currently watches the AWS DevOps and Google Cloud management-tools feeds. A scan fetches titles, descriptions, publication signals, source links, and article-page text when available; summaries are generated from that fetched text, using the OpenAI Responses API when configured or a local extractive fallback otherwise. The manual scan button remains available, and the backend also runs a startup scan when the last run is older than `SCAN_INTERVAL_HOURS` (24 by default), followed by a background daily check.

## Next integration seam

The UI is ready to connect to a LangGraph or LangChain service. The natural graph nodes are:

`collect_sources → rank_relevance → summarize → assess_readiness → generate_challenge → recommend_plan`

Suggested production adapters are RSS/Atom feeds and official blogs first, then research indexes, GitHub releases, and learning resources. Keep citations attached to every source summary and store progress events so the readiness report can evolve over time. Job and opportunity discovery belongs to the second coworker.

## Project structure

```text
.
├── backend/
│   ├── profile.json
│   └── server.py
├── config/
│   └── .env.example
├── docs/
│   └── architecture.md
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── .gitignore
├── package.json
└── README.md
```
