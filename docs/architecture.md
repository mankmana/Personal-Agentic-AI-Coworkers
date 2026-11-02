# DailyTechUpgradeAgent architecture

## Runtime flow

```text
Browser
  │
  ├── GET /api/dashboard
  ├── POST /api/scan
  ├── GET /api/challenges/next
  └── POST /api/assessments
        │
        ▼
backend/server.py
  ├── profile loader      → backend/profile.json
  ├── feed collectors     → RSS / Atom sources
  ├── summarizer          → OpenAI Responses API or fallback mode
  ├── challenge generator → article + target-role context
  ├── evaluator           → rubric + evidence signals
  └── readiness report    → backend/data/state.json
```

## Content lanes

- `general_ai_development`: AI engineering, agents, RAG, evaluation, model operations, and frontier-lab developments.
- `sre_devops_support`: SRE, DevOps, cloud infrastructure, incident response, platform engineering, support operations, and reliability practice.

Both lanes use the same pipeline, but relevance and challenge generation are personalized against the profile in `backend/profile.json`.

## Local state

`backend/data/state.json` is created at runtime and intentionally ignored by Git. It stores scan runs, submitted answers, and readiness updates. A production deployment should replace it with a database and add authentication per user.

## Provider boundary

The default server is stdlib-only. When `OPENAI_API_KEY` is present, `server.py` calls the Responses API for article summaries and structured evaluation; without it, the same endpoints work with deterministic extractive summaries and a transparent rubric-based evaluator.
