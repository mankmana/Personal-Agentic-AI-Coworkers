#!/usr/bin/env python3
"""DailyTechUpgradeAgent backend.

Stdlib-only by default so the project can run immediately. Set OPENAI_API_KEY to
replace the deterministic extractive/evaluation fallbacks with model-backed work.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
import urllib.parse
import urllib.error
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
SCAN_INTERVAL_HOURS = float(os.getenv("SCAN_INTERVAL_HOURS", "24"))
STATE_LOCK = threading.Lock()
SCHEDULER_STOP = threading.Event()


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


COMPETENCIES = [
    {"key": "operational_response", "label": "Operational execution", "weight": 0.30},
    {"key": "aws_cloud", "label": "Systems, cloud, and networking", "weight": 0.25},
    {"key": "automation_iac", "label": "Automation and infrastructure as code", "weight": 0.20},
    {"key": "reliability_systems", "label": "Reliability and systems design", "weight": 0.15},
    {"key": "communication", "label": "Communication and technical explanation", "weight": 0.10},
]


def default_state() -> dict:
    return {"articles": [], "answers": [], "runs": [], "updated_at": now_iso()}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return default_state()
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state.setdefault("articles", [])
        state.setdefault("answers", [])
        state.setdefault("runs", [])
        state["articles"] = [article for article in state["articles"] if article.get("reference") and article.get("grounded", True)]
        for article in state["articles"]:
            article["grounded"] = True
            article["source_type"] = article.get("source_type", "rss_atom")
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
            return visible_text(child.text or "")
    return ""


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked = 0
        self.block_tags = {"head", "script", "style", "noscript", "svg", "nav", "footer", "form"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.block_tags:
            self.blocked += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.block_tags and self.blocked:
            self.blocked -= 1

    def handle_data(self, data: str) -> None:
        if not self.blocked:
            self.parts.append(data)


def visible_text(raw: str) -> str:
    parser = VisibleTextParser()
    parser.feed(raw or "")
    return clean_text(" ".join(parser.parts))


def fetch_article_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "DailyTechUpgradeAgent/0.1"})
    with urllib.request.urlopen(request, timeout=6) as response:
        raw = response.read(500_000).decode("utf-8", errors="replace")
    text = visible_text(raw)
    return text[:16000]


def fetch_feed(url: str, lane: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "DailyTechUpgradeAgent/0.1"})
    with urllib.request.urlopen(request, timeout=12) as response:
        root = ET.fromstring(response.read())
    raw_items = []
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
        if not title or not link:
            continue
        raw_items.append({"title": title, "description": description, "link": link})

    page_texts = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_article_text, item["link"]): item["link"] for item in raw_items}
        for future in as_completed(futures):
            link = futures[future]
            try:
                page_text = future.result()
                page_texts[link] = page_text if len(page_text) >= 240 else ""
            except (OSError, ValueError, urllib.error.URLError):
                page_texts[link] = ""

    items = []
    source = urllib.parse.urlparse(url).netloc.replace("www.", "")
    for raw in raw_items:
        title, description, link = raw["title"], raw["description"], raw["link"]
        article_text = page_texts.get(link) or description
        if not article_text:
            continue
        article_id = hashlib.sha1(f"{title}{link}".encode()).hexdigest()[:14]
        grounding_basis = "article_page" if page_texts.get(link) else "feed_entry"
        summary = summarize_article(title, source, article_text)
        items.append({"id": f"live-{article_id}", "lane": lane, "tag": "LIVE SOURCE", "source": source, "title": title, "reference": link, "read_time": "fresh signal", "published_at": now_iso()[:10], "source_type": "rss_atom", "grounded": True, "grounding_basis": grounding_basis, **summary})
    return items[:8]


def ingest_sources(state: dict, lanes: list[str]) -> dict:
    existing_ids = {article["id"] for article in state["articles"]}
    existing_articles = {article["id"]: article for article in state["articles"]}
    fetched = 0
    refreshed = 0
    failures = []
    for lane in lanes:
        for url in feed_urls().get(lane, []):
            try:
                for article in fetch_feed(url, lane):
                    if article["id"] not in existing_ids:
                        state["articles"].insert(0, article)
                        existing_ids.add(article["id"])
                        fetched += 1
                    elif existing_articles[article["id"]].get("source_type") == "rss_atom":
                        index = next(index for index, current in enumerate(state["articles"]) if current["id"] == article["id"])
                        state["articles"][index] = article
                        refreshed += 1
            except Exception as error:
                failures.append({"url": url, "error": str(error)})
    run = {"id": f"run-{len(state['runs']) + 1:03d}", "completed_at": now_iso(), "lanes": lanes, "fetched": fetched, "refreshed": refreshed, "failures": failures, "mode": "openai_responses" if OPENAI_API_KEY else "fallback_summaries"}
    state["runs"].insert(0, run)
    state["updated_at"] = run["completed_at"]
    return run


def scan_is_due(state: dict) -> bool:
    if not state.get("runs"):
        return True
    try:
        last_scan = datetime.fromisoformat(state["runs"][0]["completed_at"])
        age_seconds = (datetime.now(timezone.utc) - last_scan).total_seconds()
        return age_seconds >= SCAN_INTERVAL_HOURS * 3600
    except (KeyError, TypeError, ValueError):
        return True


def run_scan(lanes: list[str]) -> dict:
    with STATE_LOCK:
        state = load_state()
        run = ingest_sources(state, lanes)
        save_state(state)
    return run


def scheduled_scan_loop() -> None:
    lanes = ["general_ai_development", "sre_devops_support"]
    while not SCHEDULER_STOP.is_set():
        with STATE_LOCK:
            due = scan_is_due(load_state())
        if due:
            try:
                run_scan(lanes)
            except Exception as error:
                print(f"Scheduled scan failed: {error}")
        if SCHEDULER_STOP.wait(60):
            break


def readiness_report(state: dict) -> dict:
    profile = read_profile()
    scores = dict(profile["baseline_competencies"])
    evidence = {key: 0 for key in scores}
    for answer in state.get("answers", []):
        competency = answer.get("competency", "operational_response")
        if competency in scores:
            score = float(answer.get("score", 0))
            scores[competency] = round((scores[competency] * 3 + score) / 4)
            evidence[competency] += 1
    weighted = round(sum(scores[item["key"]] * item["weight"] for item in COMPETENCIES))
    ranked = sorted(COMPETENCIES, key=lambda item: scores[item["key"]], reverse=True)
    strengths = [{"name": item["label"], "score": scores[item["key"]]} for item in ranked[:2]]
    gaps = [{"name": item["label"], "score": scores[item["key"]]} for item in ranked[-2:][::-1]]
    confidence = min(0.95, round(0.45 + sum(evidence.values()) * 0.08, 2))
    return {"overall": weighted, "confidence": confidence, "confidence_label": "high" if confidence >= .75 else "medium", "target": profile["target_roles"][0], "dimensions": [{"key": item["key"], "name": item["label"], "score": scores[item["key"]], "weight": item["weight"]} for item in COMPETENCIES], "strengths": strengths, "gaps": gaps, "evidence_count": sum(evidence.values()), "next_action": "Turn one article insight into a small implementation experiment and document what you learned."}


def next_challenge(article_id: str | None = None) -> dict:
    articles = {article["id"]: article for article in load_state()["articles"]}
    article = articles.get(article_id) if article_id else next(iter(articles.values()), None)
    if article:
        competency = "reliability_systems" if article["lane"] == "general_ai_development" else "automation_iac"
        return {"question_id": f"challenge-{article['id']}", "competency": competency, "source_article_id": article["id"], "prompt": f"Based on \"{article['title']}\", design one practical pattern or implementation decision you would use in your work. Explain the tradeoffs, what could fail, and how you would validate the result.", "rubric": ["connects the article to a concrete implementation", "explains a tradeoff or failure mode", "includes a validation or observability step", "relates the idea to a real engineering context"]}
    return {"question_id": "article-challenge-001", "competency": "reliability_systems", "source_article_id": None, "prompt": "Choose one technical idea you learned recently. Explain how you would apply it in a production system, what could fail, and how you would validate the result.", "rubric": ["connects learning to implementation", "explains a tradeoff", "includes validation", "shows practical understanding"]}


def evaluate_answer(question: dict, answer: str) -> dict:
    answer_lower = answer.lower()
    signals = [
        ["tradeoff", "failure", "risk", "constraint", "priorit"],
        ["log", "metric", "trace", "observe", "monitor", "signal", "validate", "test"],
        ["retry", "idempotent", "recover", "fallback", "rollback", "mitigat", "scale"],
        ["communicat", "owner", "document", "now", "next", "later", "follow-up", "context"],
    ]
    hits = sum(1 for group in signals if any(token in answer_lower for token in group))
    depth = sum(1 for token in ["tradeoff", "idempotent", "hypothesis", "timeline", "owner", "follow-up"] if token in answer_lower)
    score = min(100, hits * 20 + min(depth, 4) * 5)
    return {"score": score, "feedback": "Strong practical answer." if score >= 75 else "Good start. Add a clearer tradeoff, validation step, and connection to a real engineering context.", "signals_found": hits, "depth_signals": depth}


def dashboard() -> dict:
    with STATE_LOCK:
        state = load_state()
    articles = state["articles"]
    return {"profile": read_profile(), "readiness": readiness_report(state), "articles": articles[:6], "general_articles": [a for a in articles if a["lane"] == "general_ai_development"][:3], "domain_articles": [a for a in articles if a["lane"] == "sre_devops_support"][:3], "workflow": [{"id": "scout", "label": "Scout", "status": "complete"}, {"id": "synthesize", "label": "Synthesize", "status": "complete"}, {"id": "challenge", "label": "Challenge", "status": "current"}, {"id": "coach", "label": "Coach", "status": "queued"}], "last_scan": state["runs"][0] if state.get("runs") else None, "updated_at": state["updated_at"], "llm_enabled": bool(OPENAI_API_KEY), "grounding": {"source_grounded_articles": sum(1 for article in articles if article.get("grounded")), "article_page_summaries": sum(1 for article in articles if article.get("grounding_basis") == "article_page"), "feed_entry_summaries": sum(1 for article in articles if article.get("grounding_basis") == "feed_entry"), "note": "Every article returned by this API has a source URL and is summarized from fetched source text."}, "scheduler": {"enabled": True, "interval_hours": SCAN_INTERVAL_HOURS}}


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
            run = run_scan(lanes)
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
    print(f"Automatic source scan: every {SCAN_INTERVAL_HOURS:g} hours")
    with STATE_LOCK:
        save_state(load_state())
    threading.Thread(target=scheduled_scan_loop, name="daily-source-scan", daemon=True).start()
    print("Automatic source scan queued in the background")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
