#!/usr/bin/env python3
"""DailyTechUpgradeAgent backend.

Stdlib-only by default so the project can run immediately. Set OPENAI_API_KEY to
replace the deterministic extractive/evaluation fallbacks with model-backed work.
"""

from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "frontend"
DATA_DIR = ROOT / "backend" / "data"
STATE_PATH = Path(os.getenv("STATE_PATH", str(DATA_DIR / "state.json")))
PROFILE_PATH = ROOT / "backend" / "profile.json"
PORT = int(os.getenv("PORT", "4173"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/responses")
STATE_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:72]


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def read_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


SEED_ARTICLES = [
    {
        "id": "durable-execution-reliability-primitive",
        "lane": "general_ai_development",
        "tag": "FRONTIER LABS",
        "source": "Temporal Engineering",
        "title": "Why durable execution is becoming the new reliability primitive",
        "summary": "Long-running agent workflows fail differently from request/response services: they must survive retries, worker restarts, partial tool calls, and human handoffs. Durable execution frameworks externalize progress so the workflow can resume from the last safe checkpoint instead of starting over.",
        "takeaways": ["Checkpoint every side effect before moving to the next step.", "Make retries idempotent so recovery does not create duplicate work.", "Trace state transitions, not just individual service calls."],
        "why_it_matters": "SREs who can reason about failure across async systems will be well-positioned to operate agentic platforms.",
        "read_time": "7 min read",
        "published_at": "2026-11-01",
        "summary_mode": "seeded_demo",
    },
    {
        "id": "platform-team-mindset-kubernetes",
        "lane": "sre_devops_support",
        "tag": "GOOGLE CLOUD",
        "source": "Google Cloud Blog",
        "title": "Operating Kubernetes with a platform team mindset",
        "summary": "Platform engineering is moving beyond a collection of internal tools. The strongest teams build paved roads with clear ownership, observable service-level signals, and enough guardrails to reduce cognitive load without hiding operational reality.",
        "takeaways": ["Measure platform adoption and developer friction, not tool count.", "Offer a safe default path while keeping escape hatches visible.", "Treat internal platforms like products with feedback loops."],
        "why_it_matters": "Use your support background as an advantage: document one paved road that would make a recurring handoff easier for developers.",
        "read_time": "5 min read",
        "published_at": "2026-11-01",
        "summary_mode": "seeded_demo",
    },
    {
        "id": "model-call-production-incident",
        "lane": "general_ai_development",
        "tag": "OPENAI",
        "source": "OpenAI Engineering",
        "title": "Tracing the path from model call to production incident",
        "summary": "Observability for AI systems needs to connect model calls, tool use, prompt and policy decisions, cost, latency, and human escalation into one incident story. A single request trace is not enough when the system can branch, retry, or ask for help.",
        "takeaways": ["Correlate model, tool, and infrastructure spans in one trace.", "Track quality and cost signals beside latency and errors.", "Make human escalation an observable state transition."],
        "why_it_matters": "Sketch the trace context you would want during an incident involving a model call, a tool timeout, and a manual escalation.",
        "read_time": "9 min read",
        "published_at": "2026-11-01",
        "summary_mode": "seeded_demo",
    },
    {
        "id": "sre-error-budgets-and-change",
        "lane": "sre_devops_support",
        "tag": "SRE",
        "source": "SRE practice note",
        "title": "Error budgets are a decision system, not a dashboard tile",
        "summary": "An error budget becomes useful when it changes what the team does next: slow risky releases, prioritize reliability work, or accept a known tradeoff. The operational habit is to connect the budget to explicit service ownership and review rituals.",
        "takeaways": ["Define the decision an SLO breach should trigger.", "Pair reliability work with a measurable user impact.", "Review changes and incidents together instead of in separate queues."],
        "why_it_matters": "Your production support experience is a strong base for practicing how reliability signals influence prioritization.",
        "read_time": "6 min read",
        "published_at": "2026-10-31",
        "summary_mode": "seeded_demo",
    },
    {
        "id": "evaluation-loops-agent-systems",
        "lane": "general_ai_development",
        "tag": "ANTHROPIC",
        "source": "Frontier AI research",
        "title": "Evaluation loops for tool-using AI systems",
        "summary": "Agent quality cannot be measured only by whether a final answer looks correct. Evaluation needs traces, tool outcomes, retries, policy decisions, and human review so teams can identify where the system failed and whether a fix generalizes.",
        "takeaways": ["Evaluate intermediate steps as well as final outputs.", "Keep representative failure cases in a regression set.", "Separate model quality from tool and orchestration quality."],
        "why_it_matters": "This is a bridge between your RAG project experience and the operational discipline expected in AI infrastructure work.",
        "read_time": "8 min read",
        "published_at": "2026-10-30",
        "summary_mode": "seeded_demo",
    },
    {
        "id": "cloudwatch-incident-prioritization",
        "lane": "sre_devops_support",
        "tag": "AWS",
        "source": "AWS DevOps",
        "title": "From CloudWatch signal to a calmer incident response",
        "summary": "The first minutes of an incident are a prioritization problem. Strong responders combine customer impact, change history, dependency health, and the quality of the signal before choosing rollback, mitigation, or escalation.",
        "takeaways": ["Start with impact and blast radius, then investigate cause.", "Use change history as a high-value hypothesis, not a conclusion.", "Make the next update time explicit for the people coordinating response."],
        "why_it_matters": "Your Amazon Ads on-call experience maps directly to this pattern and is a strong interview story to sharpen.",
        "read_time": "5 min read",
        "published_at": "2026-10-29",
        "summary_mode": "seeded_demo",
    },
]


COMPETENCIES = [
    {"key": "incident_response", "label": "Incident response", "weight": 0.30},
    {"key": "aws_cloud", "label": "Systems, cloud, and networking", "weight": 0.25},
    {"key": "automation_iac", "label": "Automation and infrastructure as code", "weight": 0.20},
    {"key": "reliability_systems", "label": "Reliability and systems design", "weight": 0.15},
    {"key": "communication", "label": "Communication and technical explanation", "weight": 0.10},
]


def default_state() -> dict:
    return {"articles": copy.deepcopy(SEED_ARTICLES), "answers": [], "runs": [], "updated_at": now_iso()}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return default_state()
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state.setdefault("articles", copy.deepcopy(SEED_ARTICLES))
        state.setdefault("answers", [])
        state.setdefault("runs", [])
        return state
    except (OSError, json.JSONDecodeError):
        return default_state()


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def model_text(instructions: str, prompt: str) -> str | None:
    if not OPENAI_API_KEY:
        return None
    body = json.dumps({"model": OPENAI_MODEL, "instructions": instructions, "input": prompt}).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_BASE_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("output_text"):
            return payload["output_text"]
        text_parts = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text_parts.append(content.get("text", ""))
        return "\n".join(text_parts).strip() or None
    except Exception:
        return None


def summarize_article(title: str, source: str, body: str) -> dict:
    prompt = f"""Summarize this technical article for a DevOps/SRE engineer who is also learning AI development.
Return valid JSON with keys: summary (2-3 sentences), takeaways (3 short strings), why_it_matters (1 sentence).
Title: {title}
Source: {source}
Article text: {body[:12000]}"""
    output = model_text("You are a precise technical editor. Do not invent claims or citations.", prompt)
    if output:
        try:
            parsed = json.loads(output)
            if isinstance(parsed.get("takeaways"), list):
                return {**parsed, "summary_mode": "openai_responses"}
        except json.JSONDecodeError:
            pass
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(body))
    fallback = " ".join(sentences[:3]).strip() or "The source was collected and is ready for review."
    return {
        "summary": fallback[:620],
        "takeaways": ["Read the source for implementation details.", "Connect the idea to an operational failure mode.", "Turn one insight into a small practice task."],
        "why_it_matters": "Use the idea as a prompt for a practical SRE, DevOps, or AI systems exercise.",
        "summary_mode": "extractive_fallback",
    }


def feed_urls() -> dict[str, list[str]]:
    defaults = {
        "general_ai_development": ["https://openai.com/news/rss.xml", "https://blog.google/technology/ai/rss/"],
        "sre_devops_support": ["https://aws.amazon.com/blogs/devops/feed/", "https://cloud.google.com/blog/products/management-tools/rss"],
    }
    for lane, env_name in [("general_ai_development", "GENERAL_FEEDS"), ("sre_devops_support", "DOMAIN_FEEDS")]:
        if os.getenv(env_name):
            defaults[lane] = [url.strip() for url in os.getenv(env_name, "").split(",") if url.strip()]
    return defaults


def element_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(element):
        if child.tag.rsplit("}", 1)[-1].lower() in names:
            return clean_text(child.text or "")
    return ""


def fetch_feed(url: str, lane: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "DailyTechUpgradeAgent/0.1"})
    with urllib.request.urlopen(request, timeout=12) as response:
        root = ET.fromstring(response.read())
    items = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
            continue
        title = element_text(item, ("title",))
        description = element_text(item, ("description", "summary", "content"))
        link = element_text(item, ("link",))
        if not link:
            for child in list(item):
                if child.tag.rsplit("}", 1)[-1].lower() == "link":
                    link = child.attrib.get("href", "")
        if not title:
            continue
        source = urllib.parse.urlparse(url).netloc.replace("www.", "")
        article_id = hashlib.sha1(f"{title}{link}".encode()).hexdigest()[:14]
        summary = summarize_article(title, source, description)
        items.append({"id": f"live-{article_id}", "lane": lane, "tag": "LIVE SOURCE", "source": source, "title": title, "reference": link, "read_time": "fresh signal", "published_at": now_iso()[:10], **summary})
    return items[:8]


def ingest_sources(state: dict, lanes: list[str]) -> dict:
    existing_ids = {article["id"] for article in state["articles"]}
    fetched = 0
    failures = []
    for lane in lanes:
        for url in feed_urls().get(lane, []):
            try:
                for article in fetch_feed(url, lane):
                    if article["id"] not in existing_ids:
                        state["articles"].insert(0, article)
                        existing_ids.add(article["id"])
                        fetched += 1
            except Exception as error:
                failures.append({"url": url, "error": str(error)})
    run = {"id": f"run-{len(state['runs']) + 1:03d}", "completed_at": now_iso(), "lanes": lanes, "fetched": fetched, "failures": failures, "mode": "openai_responses" if OPENAI_API_KEY else "fallback_summaries"}
    state["runs"].insert(0, run)
    state["updated_at"] = run["completed_at"]
    return run


def readiness_report(state: dict) -> dict:
    profile = read_profile()
    scores = dict(profile["baseline_competencies"])
    evidence = {key: 0 for key in scores}
    for answer in state.get("answers", []):
        competency = answer.get("competency", "incident_response")
        if competency in scores:
            score = float(answer.get("score", 0))
            scores[competency] = round((scores[competency] * 3 + score) / 4)
            evidence[competency] += 1
    weighted = round(sum(scores[item["key"]] * item["weight"] for item in COMPETENCIES))
    ranked = sorted(COMPETENCIES, key=lambda item: scores[item["key"]], reverse=True)
    strengths = [{"name": item["label"], "score": scores[item["key"]]} for item in ranked[:2]]
    gaps = [{"name": item["label"], "score": scores[item["key"]]} for item in ranked[-2:][::-1]]
    confidence = min(0.95, round(0.45 + sum(evidence.values()) * 0.08, 2))
    return {"overall": weighted, "confidence": confidence, "confidence_label": "high" if confidence >= .75 else "medium", "target": profile["target_roles"][0], "dimensions": [{"key": item["key"], "name": item["label"], "score": scores[item["key"]], "weight": item["weight"]} for item in COMPETENCIES], "strengths": strengths, "gaps": gaps, "evidence_count": sum(evidence.values()), "next_action": "Practice a blameless incident narrative with a clear now / next / later structure."}


def opportunity_list() -> list[dict]:
    return [
        {"title": "Site Reliability Engineer", "company": "Cloud platform team", "fit": 92, "reason": "Matches Amazon on-call, CloudWatch, incident response, and cross-service debugging evidence."},
        {"title": "Platform Engineer", "company": "Developer infrastructure team", "fit": 88, "reason": "Strong fit for automation, internal support, CI/CD, and the path toward paved platform roads."},
        {"title": "AI Infrastructure Engineer", "company": "Applied AI startup", "fit": 76, "reason": "Connects your RAG project and operations experience; deepen evals, tracing, and distributed systems."},
        {"title": "Cloud Operations Engineer", "company": "Enterprise systems team", "fit": 84, "reason": "Builds on regulated-system support, migrations, AWS, and production troubleshooting."},
    ]


def next_challenge(article_id: str | None = None) -> dict:
    articles = {article["id"]: article for article in load_state()["articles"]}
    article = articles.get(article_id) if article_id else None
    if article and article["lane"] == "general_ai_development":
        return {"question_id": f"challenge-{article['id']}", "competency": "reliability_systems", "source_article_id": article["id"], "prompt": f"Based on \"{article['title']}\", design one failure-safe pattern you would use in a production workflow. Explain what can fail, how the system recovers, and what you would observe.", "rubric": ["names a concrete failure mode", "proposes a recovery or idempotency strategy", "includes observability", "explains a tradeoff"]}
    return {"question_id": "incident-command-001", "competency": "incident_response", "source_article_id": article["id"] if article else None, "prompt": "A checkout service is returning intermittent 502s. Error rate is 3%, latency is climbing, and the last deploy was 20 minutes ago. Walk through your first 10 minutes.", "rubric": ["prioritizes customer impact and blast radius", "checks change history and service signals", "chooses mitigation or rollback deliberately", "communicates now, next, and later"]}


def evaluate_answer(question: dict, answer: str) -> dict:
    answer_lower = answer.lower()
    signals = [
        ["impact", "blast radius", "customer", "severity", "priorit"],
        ["log", "metric", "trace", "dependency", "cloudwatch", "dashboard", "deploy"],
        ["rollback", "mitigat", "pause", "feature flag", "scale", "failover"],
        ["communicat", "status", "now", "next", "later", "escalat"],
    ]
    hits = sum(1 for group in signals if any(token in answer_lower for token in group))
    depth = sum(1 for token in ["tradeoff", "idempotent", "hypothesis", "timeline", "owner", "follow-up"] if token in answer_lower)
    score = min(100, hits * 20 + min(depth, 4) * 5)
    return {"score": score, "feedback": "Strong operational answer." if score >= 75 else "Good start. Add clearer prioritization, evidence, and follow-up ownership.", "signals_found": hits, "depth_signals": depth}


def dashboard() -> dict:
    with STATE_LOCK:
        state = load_state()
    articles = state["articles"]
    return {"profile": read_profile(), "readiness": readiness_report(state), "articles": articles[:6], "general_articles": [a for a in articles if a["lane"] == "general_ai_development"][:3], "domain_articles": [a for a in articles if a["lane"] == "sre_devops_support"][:3], "opportunities": opportunity_list(), "workflow": [{"id": "scout", "label": "Scout", "status": "complete"}, {"id": "synthesize", "label": "Synthesize", "status": "complete"}, {"id": "challenge", "label": "Challenge", "status": "current"}, {"id": "coach", "label": "Coach", "status": "queued"}], "last_scan": state["runs"][0] if state.get("runs") else None, "updated_at": state["updated_at"], "llm_enabled": bool(OPENAI_API_KEY)}


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", os.getenv("CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return super().do_GET()
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "service": "DailyTechUpgradeAgent", "llm_enabled": bool(OPENAI_API_KEY), "time": now_iso()})
        if parsed.path == "/api/profile":
            return self.send_json(read_profile())
        if parsed.path == "/api/dashboard":
            return self.send_json(dashboard())
        if parsed.path == "/api/report":
            with STATE_LOCK:
                return self.send_json(readiness_report(load_state()))
        if parsed.path == "/api/articles":
            lane = urllib.parse.parse_qs(parsed.query).get("lane", ["all"])[0]
            articles = dashboard()["articles"] if lane == "all" else [a for a in dashboard()["articles"] if a["lane"] == lane]
            return self.send_json({"articles": articles, "lane": lane})
        if parsed.path == "/api/challenges/next":
            article_id = urllib.parse.parse_qs(parsed.query).get("article_id", [None])[0]
            return self.send_json(next_challenge(article_id))
        return self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/scan":
            payload = self.read_json()
            lanes = payload.get("lanes", ["general_ai_development", "sre_devops_support"])
            with STATE_LOCK:
                state = load_state()
                run = ingest_sources(state, lanes)
                save_state(state)
            return self.send_json({"run": run, "dashboard": dashboard()})
        if parsed.path == "/api/assessments":
            payload = self.read_json()
            answer = clean_text(payload.get("answer", ""))
            if len(answer) < 20:
                return self.send_json({"error": "Answer must be at least 20 characters."}, 400)
            question = payload.get("question") or next_challenge(payload.get("article_id"))
            result = evaluate_answer(question, answer)
            result.update({"question_id": question["question_id"], "competency": question["competency"], "answer": answer, "submitted_at": now_iso()})
            with STATE_LOCK:
                state = load_state()
                state["answers"].insert(0, result)
                state["updated_at"] = result["submitted_at"]
                save_state(state)
                report = readiness_report(state)
            return self.send_json({"assessment": result, "readiness": report})
        return self.send_json({"error": "Not found"}, 404)


def main():
    os.chdir(FRONTEND_ROOT)
    print(f"DailyTechUpgradeAgent backend running at http://localhost:{PORT}")
    print(f"OpenAI Responses integration: {'enabled' if OPENAI_API_KEY else 'disabled (fallback mode)'}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
