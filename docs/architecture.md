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

- `general_ai_development`: AI engineering, agents, RAG, evaluation, model operations, research, developer tooling, and frontier-lab/company developments across OpenAI, Google, Apple, AWS, Netflix, Anthropic, and Meta sources.
- `sre_devops_support`: SRE, DevOps, cloud infrastructure, incident response, platform engineering, support operations, and reliability practice.

Both lanes use the same pipeline, but relevance and challenge generation are personalized against the profile in `backend/profile.json`.

## Responsibility boundary

`DailyTechUpgradeAgent` owns technical signals, article summaries, article-grounded challenges, and readiness evidence. It does not collect or rank jobs, internships, research roles, or entrepreneurial opportunities. Those opportunity workflows belong to `NextLevelPersonalCoachForCareerLevel`.

`NextLevelPersonalCoachForCareerLevel` stores its own opportunity state in `backend/data/opportunities.json`, filters postings against the target internship roles and resume skills, generates a preparation plan for a selected posting, evaluates practice answers, and records saved/applied/preparation activity. Its first source adapter accepts public RSS/Atom or employer ATS feeds configured with `JOB_FEEDS`. It does not bypass authentication or anti-bot controls on LinkedIn, Indeed, or Glassdoor.

## Source grounding

The backend does not serve seeded article cards. A successful RSS/Atom ingestion creates `source_type: rss_atom`; official Anthropic and Meta article-index ingestion creates `source_type: html_index`. Both retain the source `reference` URL, fetch linked article-page text when possible, and record `grounding_basis` as `article_page` or `feed_entry`. Every article returned by the API has a source URL and is marked grounded.

## Daily refresh

`POST /api/scan` performs an immediate scan for the selected lanes. On startup, the server scans if the last run is older than `SCAN_INTERVAL_HOURS` (24 hours by default). A daemon scheduler checks once per minute and runs the same scan when the interval is due. Set `SCAN_INTERVAL_HOURS` to change the cadence.

## Learning momentum

The dashboard challenge is independent of the removed Career Readiness UI. `GET /api/learning` returns one challenge based on the latest grounded article plus the current streak. `POST /api/learning/complete` records one completed challenge per local calendar day using `USER_TIMEZONE` (America/Los_Angeles by default). The streak and week-over-week delta are calculated from persisted completion dates rather than hardcoded values.

## Local state

`backend/data/state.json` is created at runtime and intentionally ignored by Git. It stores scan runs, submitted answers, and readiness updates. A production deployment should replace it with a database and add authentication per user.

## Provider boundary

The default server is stdlib-only. When `OPENAI_API_KEY` is present, `server.py` calls the Responses API for article summaries and structured evaluation; without it, the same endpoints work with deterministic extractive summaries and a transparent rubric-based evaluator.
