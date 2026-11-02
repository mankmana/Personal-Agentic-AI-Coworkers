# Personal Agentic AI Coworkers

A small, buildless dashboard prototype for two career-focused AI coworkers:

1. **DailyTechUpgradeAgent** — the active coworker that watches the SRE, DevOps, and software support landscape, turns technical signals into a daily brief, and coaches you toward your next opportunity.
2. **NextLevelPersonalCoachForCareerLevel** — the planned second coworker for broader career planning and accountability.

The first pass is intentionally front-end only. It uses realistic seeded data so the workflow and product experience are easy to evaluate before wiring in external APIs or an agent runtime.

## Run locally

This project has no build step or dependency install requirement.

```bash
python3 -m http.server 4173
```

Then open [http://localhost:4173](http://localhost:4173).

## What is included

- Overview dashboard with readiness, momentum, opportunities, and daily top-three brief.
- Simulated agent workflow showing the stages from signal scan to personalized coaching.
- Technical radar for SRE, DevOps, support engineering, and frontier-lab developments.
- Career lab with a readiness snapshot, technical assessment prompts, and a focused improvement plan.
- Responsive layout with no external assets or frameworks.

## Next integration seam

The UI is ready to connect to a LangGraph or LangChain service. The natural graph nodes are:

`collect_sources → rank_relevance → summarize → assess_readiness → generate_challenge → recommend_plan`

Suggested production adapters are RSS/Atom feeds and official blogs first, then job boards, GitHub, arXiv, and OpenAI Responses API tools. Keep citations attached to every source summary and store progress events so the readiness report can evolve over time.

## Project structure

```text
.
├── index.html
├── styles.css
├── app.js
├── package.json
└── README.md
```
