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
from datetime import date, datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo


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
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "America/Los_Angeles")
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
    return {"articles": [], "answers": [], "learning_activity": [], "runs": [], "updated_at": now_iso()}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return default_state()
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state.setdefault("articles", [])
        state.setdefault("answers", [])
        state.setdefault("learning_activity", [])
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


def summarize_article(title: str, source: str, body: str, lane: str = "general_ai_development") -> dict:
    audience = "AI/software engineering and research readers" if lane == "general_ai_development" else "an SRE, DevOps, cloud, or software support engineer"
    prompt = f"""Summarize this technical article for {audience}.
Do not force an SRE or DevOps angle onto general AI, research, or product-development articles. Explain the actual development first, then its practical relevance.
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
        "why_it_matters": "Use the idea as a prompt for a practical software, AI, research, or operations exercise.",
        "summary_mode": "extractive_fallback",
    }


def feed_urls() -> dict[str, list[str]]:
    defaults = {
        "general_ai_development": [
            "https://openai.com/news/rss.xml",
            "https://blog.google/technology/ai/rss/",
            "https://research.google/blog/rss/",
            "https://machinelearning.apple.com/rss.xml",
            "https://aws.amazon.com/blogs/machine-learning/feed/",
            "https://netflixtechblog.com/feed",
        ],
        "sre_devops_support": [
            "https://aws.amazon.com/blogs/devops/feed/",
        ],
    }
    for lane, env_name in [("general_ai_development", "GENERAL_FEEDS"), ("sre_devops_support", "DOMAIN_FEEDS")]:
        if os.getenv(env_name):
            defaults[lane] = [url.strip() for url in os.getenv(env_name, "").split(",") if url.strip()]
    return defaults


def web_index_urls() -> dict[str, list[str]]:
    return {
        "general_ai_development": ["https://www.anthropic.com/news", "https://ai.meta.com/blog"],
        "sre_devops_support": ["https://cloud.google.com/blog/products/devops-sre"],
    }


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
        self.block_tags = {"head", "script", "style", "noscript", "svg", "nav", "header", "aside", "menu", "footer", "form"}

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


class ArticleLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_href = ""
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a" or self.current_href:
            return
        attributes = dict(attrs)
        self.current_href = attributes.get("href") or ""
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.current_href:
            title = clean_text(" ".join(self.current_text))
            if title and self.current_href:
                self.links.append((title, self.current_href))
            self.current_href = ""
            self.current_text = []


def fetch_web_index(url: str, lane: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DailyTechUpgradeAgent/0.1"})
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = response.read(1_000_000).decode("utf-8", errors="replace")
    parser = ArticleLinkParser()
    parser.feed(raw)
    host = urllib.parse.urlparse(url).netloc
    candidates = []
    seen = set()
    for title, href in parser.links:
        link = urllib.parse.urljoin(url, href).split("#", 1)[0]
        path = urllib.parse.urlparse(link).path.rstrip("/")
        if host.endswith("anthropic.com"):
            valid = path.startswith("/news/") and path.count("/") >= 2 and path not in {"/news/announcements", "/news/features"}
        elif host.endswith("meta.com"):
            valid = path.startswith("/blog/") and path.count("/") >= 2
        elif host.endswith("cloud.google.com"):
            valid = path.startswith("/blog/products/devops-sre/") and path.count("/") >= 4
        else:
            valid = False
        if valid and link not in seen and len(title) >= 12:
            seen.add(link)
            candidates.append({"title": title, "link": link})
    page_texts = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_article_text, item["link"]): item["link"] for item in candidates[:12]}
        for future in as_completed(futures):
            link = futures[future]
            try:
                page_text = future.result()
                page_texts[link] = page_text if len(page_text) >= 240 else ""
            except (OSError, ValueError, urllib.error.URLError):
                page_texts[link] = ""
    source = urllib.parse.urlparse(url).netloc.replace("www.", "")
    items = []
    for candidate in candidates[:12]:
        link = candidate["link"]
        article_text = page_texts.get(link, "")
        if not article_text:
            continue
        title = candidate["title"]
        article_id = hashlib.sha1(f"{title}{link}".encode()).hexdigest()[:14]
        summary = summarize_article(title, source, article_text, lane)
        items.append({"id": f"live-{article_id}", "lane": lane, "tag": "LIVE SOURCE", "source": source, "title": title, "reference": link, "read_time": "fresh signal", "published_at": now_iso()[:10], "source_type": "html_index", "grounded": True, "grounding_basis": "article_page", **summary})
    return items[:8]


def fetch_feed(url: str, lane: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "DailyTechUpgradeAgent/0.1"})
    with urllib.request.urlopen(request, timeout=12) as response:
        root = ET.fromstring(response.read())
    raw_items = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
            continue
        title = element_text(item, ("title",))
        description = element_text(item, ("description", "summary", "content", "encoded"))
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
        summary = summarize_article(title, source, article_text, lane)
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
                    elif existing_articles[article["id"]].get("source_type") in {"rss_atom", "html_index"}:
                        index = next(index for index, current in enumerate(state["articles"]) if current["id"] == article["id"])
                        state["articles"][index] = article
                        refreshed += 1
            except Exception as error:
                failures.append({"url": url, "error": str(error)})
        for url in web_index_urls().get(lane, []):
            try:
                for article in fetch_web_index(url, lane):
                    if article["id"] not in existing_ids:
                        state["articles"].insert(0, article)
                        existing_ids.add(article["id"])
                        fetched += 1
                    elif existing_articles[article["id"]].get("source_type") in {"rss_atom", "html_index"}:
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


def challenge_for_article(article: dict | None) -> dict:
    if article:
        competency = "reliability_systems" if article["lane"] == "general_ai_development" else "automation_iac"
        title = article["title"]
        summary = article.get("summary", "the main development described in the source")
        questions = [
            {"question_id": f"challenge-{article['id']}-q1", "type": "understand", "prompt": f"According to \"{title}\", what is the main technical development?", "options": [summary[:180], "A manual-only process that removes automation from the workflow.", "A user-interface redesign unrelated to engineering operations.", "A hardware-only capacity upgrade with no software change."], "correct_option": 0},
            {"question_id": f"challenge-{article['id']}-q2", "type": "apply", "prompt": "Which SRE or DevOps use of this idea is the most practical?", "options": ["Adopt it everywhere immediately without testing or ownership.", "Run it in a bounded workflow with clear permissions, logs, alerts, and an operator fallback.", "Use it only as a presentation topic without connecting it to a system.", "Remove monitoring because the automation is expected to be reliable."], "correct_option": 1},
            {"question_id": f"challenge-{article['id']}-q3", "type": "evaluate", "prompt": "What is the strongest way to validate an operational rollout of this idea?", "options": ["Measure only how quickly the first demo works.", "Deploy it directly to every production system and wait for user complaints.", "Use a staged test with success metrics, logs or traces, security checks, and a rollback path.", "Skip validation when the source article reports positive results."], "correct_option": 2},
        ]
        return {"question_id": f"challenge-{article['id']}", "competency": competency, "source_article_id": article["id"], "source_summary": summary, "source_title": title, "prompt": questions[0]["prompt"], "questions": questions, "question_count": len(questions)}
    questions = [
        {"question_id": "article-challenge-001-q1", "type": "understand", "prompt": "What should you identify first when learning a new technical development?", "options": ["The problem it solves and the evidence supporting it.", "Only the product logo and launch date.", "A way to avoid reading the source material.", "A production deployment with no requirements."], "correct_option": 0},
        {"question_id": "article-challenge-001-q2", "type": "apply", "prompt": "Which SRE or DevOps application is the safest starting point?", "options": ["A bounded workflow with permissions, monitoring, and human fallback.", "An unreviewed change to every production service.", "A workflow with no owner or alerting.", "A demo that cannot be measured."], "correct_option": 0},
        {"question_id": "article-challenge-001-q3", "type": "evaluate", "prompt": "How should you validate the idea before broad adoption?", "options": ["Use a staged test with metrics, logs or traces, security checks, and rollback.", "Skip testing if the idea sounds promising.", "Measure only the number of tools involved.", "Wait for an incident before adding observability."], "correct_option": 0},
    ]
    return {"question_id": "article-challenge-001", "competency": "reliability_systems", "source_article_id": None, "source_title": "No grounded article loaded", "prompt": questions[0]["prompt"], "questions": questions, "question_count": len(questions)}


def public_challenge(challenge: dict) -> dict:
    public = dict(challenge)
    public["questions"] = [{key: value for key, value in question.items() if key != "correct_option"} for question in challenge.get("questions", [])]
    return public


def next_challenge(article_id: str | None = None) -> dict:
    articles = {article["id"]: article for article in load_state()["articles"]}
    article = articles.get(article_id) if article_id else next(iter(articles.values()), None)
    return challenge_for_article(article)


def local_today() -> date:
    try:
        return datetime.now(ZoneInfo(USER_TIMEZONE)).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def learning_stats(state: dict) -> dict:
    today = local_today()
    completed_dates = set()
    for item in state.get("learning_activity", []):
        try:
            completed_dates.add(date.fromisoformat(item["date"]))
        except (KeyError, TypeError, ValueError):
            continue

    cursor = today if today in completed_dates else today - timedelta(days=1)
    streak = 0
    while cursor in completed_dates:
        streak += 1
        cursor -= timedelta(days=1)
    current_week = sum(1 for offset in range(7) if today - timedelta(days=offset) in completed_dates)
    previous_week = sum(1 for offset in range(7, 14) if today - timedelta(days=offset) in completed_dates)
    article = state["articles"][0] if state.get("articles") else None
    full_challenge = challenge_for_article(article)
    challenge = public_challenge(full_challenge)
    challenge["source_title"] = article["title"] if article else "No grounded article loaded"
    challenge["source"] = article["source"] if article else "DailyTechUpgradeAgent"
    today_activity = next((item for item in state.get("learning_activity", []) if item.get("date") == today.isoformat()), None)
    quiz_results = []
    if today_activity:
        for index, result in enumerate(today_activity.get("results", [])):
            enriched = dict(result)
            if index < len(full_challenge.get("questions", [])):
                expected = full_challenge["questions"][index].get("correct_option")
                enriched["correct_option"] = expected
                enriched["correct"] = enriched.get("selected_option") == expected
                enriched["score"] = 100 if enriched["correct"] else 0
            quiz_results.append(enriched)
    return {"streak_days": streak, "week_delta": current_week - previous_week, "completed_today": today in completed_dates, "completed_days": [today - timedelta(days=offset) in completed_dates for offset in range(6, -1, -1)], "challenge": challenge, "quiz_score": today_activity.get("score") if today_activity else None, "quiz_results": quiz_results, "timezone": USER_TIMEZONE}


def complete_learning_activity(state: dict, article_id: str | None, answers: list[str]) -> dict:
    today = local_today().isoformat()
    for item in state["learning_activity"]:
        if item.get("date") == today:
            return learning_stats(state)
    articles = {article["id"]: article for article in state.get("articles", [])}
    challenge = challenge_for_article(articles.get(article_id))
    questions = challenge.get("questions", [])
    results = [{"selected_option": answer, "correct_option": question.get("correct_option"), "correct": answer == question.get("correct_option"), "score": 100 if answer == question.get("correct_option") else 0} for question, answer in zip(questions, answers)]
    score = round(sum(result["score"] for result in results) / len(results)) if results else 0
    state["learning_activity"].insert(0, {"date": today, "article_id": article_id, "activity": "daily_quiz_completed", "answers": answers, "results": results, "score": score, "completed_at": now_iso()})
    state["updated_at"] = now_iso()
    return learning_stats(state)


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


def diverse_articles(articles: list[dict], limit: int) -> list[dict]:
    by_source: dict[str, list[dict]] = {}
    for article in articles:
        by_source.setdefault(article.get("source", "unknown"), []).append(article)
    selected = []
    while len(selected) < limit and by_source:
        for source in list(by_source):
            bucket = by_source[source]
            if bucket:
                selected.append(bucket.pop(0))
            if not bucket:
                by_source.pop(source, None)
            if len(selected) >= limit:
                break
    return selected


def dashboard() -> dict:
    with STATE_LOCK:
        state = load_state()
    articles = state["articles"]
    general_articles = diverse_articles([article for article in articles if article["lane"] == "general_ai_development"], len(articles))
    domain_articles = diverse_articles([article for article in articles if article["lane"] == "sre_devops_support"], len(articles))
    mixed_articles = []
    for index in range(max(len(general_articles), len(domain_articles))):
        if index < len(general_articles):
            mixed_articles.append(general_articles[index])
        if index < len(domain_articles):
            mixed_articles.append(domain_articles[index])
    return {"profile": read_profile(), "readiness": readiness_report(state), "learning": learning_stats(state), "articles": mixed_articles[:6], "general_articles": general_articles[:3], "domain_articles": domain_articles[:3], "workflow": [{"id": "scout", "label": "Scout", "status": "complete"}, {"id": "synthesize", "label": "Synthesize", "status": "complete"}, {"id": "challenge", "label": "Challenge", "status": "current"}, {"id": "coach", "label": "Coach", "status": "queued"}], "last_scan": state["runs"][0] if state.get("runs") else None, "updated_at": state["updated_at"], "llm_enabled": bool(OPENAI_API_KEY), "grounding": {"source_grounded_articles": sum(1 for article in articles if article.get("grounded")), "article_page_summaries": sum(1 for article in articles if article.get("grounding_basis") == "article_page"), "feed_entry_summaries": sum(1 for article in articles if article.get("grounding_basis") == "feed_entry"), "note": "Every article returned by this API has a source URL and is summarized from fetched source text."}, "scheduler": {"enabled": True, "interval_hours": SCAN_INTERVAL_HOURS}}


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", os.getenv("CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, max-age=0")
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
            with STATE_LOCK:
                stored_articles = load_state()["articles"]
            articles = stored_articles if lane == "all" else [article for article in stored_articles if article["lane"] == lane]
            return self.send_json({"articles": articles, "lane": lane})
        if parsed.path == "/api/learning":
            with STATE_LOCK:
                return self.send_json(learning_stats(load_state()))
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
        if parsed.path == "/api/learning/complete":
            payload = self.read_json()
            raw_answers = payload.get("answers")
            if not isinstance(raw_answers, list):
                raw_answers = []
            if len(raw_answers) != 3 or any(not isinstance(answer, int) or answer < 0 or answer > 3 for answer in raw_answers):
                return self.send_json({"error": "Choose one option for all 3 questions."}, 400)
            with STATE_LOCK:
                state = load_state()
                learning = complete_learning_activity(state, payload.get("article_id"), raw_answers)
                save_state(state)
            return self.send_json({"learning": learning})
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
