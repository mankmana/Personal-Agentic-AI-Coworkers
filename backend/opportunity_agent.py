"""Opportunity discovery and preparation logic for NextLevel Coach.

The collector accepts public RSS/Atom feeds and employer ATS feeds supplied in
JOB_FEEDS. It deliberately does not bypass authentication, bot protection, or
robots restrictions on LinkedIn, Indeed, or Glassdoor. Those sources can be
connected through an official API, export, or alert feed later.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


TARGET_ROLES = [
    "Production Engineer Intern",
    "Customer Solutions Engineer Intern",
    "Technical Support Engineer Intern",
    "DevOps Engineer Intern",
    "Production Support Engineer Intern",
]
# These are public employer job-board endpoints, not authenticated candidate
# accounts. They are a starting set and can be replaced/extended with JOB_FEEDS.
DEFAULT_PUBLIC_ATS_SOURCES = [
    "lever://palantir",
    "lever://anavationllc",
    "lever://shopback-2",
    "lever://csit",
]
INTERNSHIP_TERMS = ("intern", "internship", "co-op", "co op")
ROLE_TERMS = {
    "Production Engineer Intern": ("production engineer", "production engineering"),
    "Customer Solutions Engineer Intern": ("customer solutions", "solutions engineer", "customer engineer"),
    "Technical Support Engineer Intern": ("technical support", "support engineer", "support engineering"),
    "DevOps Engineer Intern": ("devops", "developer operations", "platform engineer", "infrastructure engineer", "cloud engineer", "cloud computing"),
    "Production Support Engineer Intern": ("production support", "application support", "site reliability", "sre"),
}
PROFILE_TERMS = ("python", "java", "shell", "aws", "cloudwatch", "linux", "kubernetes", "terraform", "ci/cd", "api", "sql", "incident")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def contains_term(text: str, term: str) -> bool:
    """Match words instead of substrings such as intern inside internal."""
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text.lower()))


def default_state() -> dict:
    return {"opportunities": [], "runs": [], "selected_id": None, "activities": [], "updated_at": now_iso()}


def load_state(path: Path) -> dict:
    if not path.exists():
        return default_state()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        for key, value in default_state().items():
            state.setdefault(key, value)
        return state
    except (OSError, json.JSONDecodeError):
        return default_state()


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def configured_feeds() -> list[str]:
    raw = os.getenv("JOB_FEEDS", "")
    configured = [url.strip() for url in raw.split(",") if url.strip()]
    if configured:
        return configured
    return list(DEFAULT_PUBLIC_ATS_SOURCES)


def element_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(element):
        if child.tag.rsplit("}", 1)[-1].lower() in names:
            return clean_text(child.text or "")
    return ""


def fetch_url(url: str, timeout: int = 12) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "NextLevelPersonalCoach/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(500_000).decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 12) -> dict | list:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "NextLevelPersonalCoach/0.1 (public job board reader)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(8_000_000).decode("utf-8", errors="replace"))


def date_from_value(value) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()
    value = clean_text(str(value or ""))
    if value:
        match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
        if match:
            return match.group(1)
    return now_iso()[:10]


def role_match(title: str, description: str) -> tuple[str, int, list[str]]:
    text = f"{title} {description}".lower()
    best_role = TARGET_ROLES[0]
    best_hits: tuple[int, list[str]] = (-1, [])
    for role, terms in ROLE_TERMS.items():
        hits = [term for term in terms if contains_term(text, term)]
        if len(hits) > best_hits[0]:
            best_role, best_hits = role, (len(hits), hits)
    score = min(100, best_hits[0] * 28 + (22 if any(contains_term(text, term) for term in INTERNSHIP_TERMS) else 0) + min(20, sum(contains_term(text, term) for term in PROFILE_TERMS) * 3))
    return best_role, score, best_hits[1]


def normalize_job(title: str, link: str, description: str, source: str, published_at=None, source_type="rss_atom") -> dict | None:
    title = clean_text(title)
    description = clean_text(description)
    if not title or not link:
        return None
    role, score, role_hits = role_match(title, description)
    text = f"{title} {description}".lower()
    if not any(contains_term(text, term) for term in INTERNSHIP_TERMS) or not role_hits:
        return None
    matched_skills = [term for term in PROFILE_TERMS if contains_term(text, term)]
    job_id = f"job-{hashlib.sha1(f'{title}{link}'.encode()).hexdigest()[:14]}"
    return {
        "id": job_id,
        "title": title,
        "company": source,
        "source": source,
        "reference": link,
        "description": description[:1800],
        "matched_role": role,
        "match_score": score,
        "matched_skills": matched_skills,
        "role_signals": role_hits,
        "grounded": True,
        "source_type": source_type,
        "published_at": date_from_value(published_at),
        "why_match": f"Matches your {role} target through {', '.join(matched_skills[:4]) or 'your operations and software background'}.",
    }


def fetch_feed(url: str) -> list[dict]:
    parsed = urllib.parse.urlparse(url)
    source_scheme = parsed.scheme.lower()
    if source_scheme in {"greenhouse", "lever"}:
        return fetch_public_ats(url)
    root = ET.fromstring(fetch_url(url))
    source = urllib.parse.urlparse(url).netloc.replace("www.", "")
    jobs = []
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
        job = normalize_job(title, link, description, source, source_type="rss_atom")
        if job:
            jobs.append(job)
    return jobs[:50]


def fetch_public_ats(source: str) -> list[dict]:
    """Read a public employer ATS board using greenhouse:// or lever:// syntax."""
    parsed = urllib.parse.urlparse(source)
    board = parsed.netloc or parsed.path.lstrip("/")
    if not board:
        raise ValueError(f"Missing ATS board name in {source}")

    jobs = []
    if parsed.scheme.lower() == "greenhouse":
        payload = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(board)}/jobs?content=true")
        for item in payload.get("jobs", []) if isinstance(payload, dict) else []:
            content = item.get("content", "")
            location = (item.get("location") or {}).get("name", "")
            departments = ", ".join(department.get("name", "") for department in item.get("departments", []))
            description = " | ".join(part for part in (location, departments, content) if part)
            job = normalize_job(
                item.get("title", ""),
                item.get("absolute_url", ""),
                description,
                f"Greenhouse · {board}",
                item.get("updated_at"),
                source_type="greenhouse_public",
            )
            if job:
                jobs.append(job)
    elif parsed.scheme.lower() == "lever":
        payload = fetch_json(f"https://api.lever.co/v0/postings/{urllib.parse.quote(board)}?mode=json")
        for item in payload if isinstance(payload, list) else []:
            categories = item.get("categories") or {}
            location = categories.get("location", "")
            commitment = categories.get("commitment", "")
            description = " | ".join(
                part for part in (
                    location,
                    commitment,
                    item.get("descriptionPlain", ""),
                    item.get("additionalPlain", ""),
                ) if part
            )
            job = normalize_job(
                item.get("text", ""),
                item.get("hostedUrl") or item.get("applyUrl") or "",
                description,
                f"Lever · {board}",
                item.get("createdAt") or item.get("updatedAt"),
                source_type="lever_public",
            )
            if job:
                jobs.append(job)
    return jobs[:100]


def is_relevant_job(job: dict) -> bool:
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    return bool(job.get("role_signals")) and any(contains_term(text, term) for term in INTERNSHIP_TERMS)


def scan(state: dict) -> dict:
    # Remove records that came from older, looser matching rules before merging
    # the current source snapshot. Saved/applied status is retained for valid
    # records because it belongs to the user's workflow.
    state["opportunities"] = [job for job in state["opportunities"] if is_relevant_job(job)]
    existing = {job["id"]: job for job in state["opportunities"]}
    fetched = 0
    refreshed = 0
    failures = []
    feeds = configured_feeds()
    for url in feeds:
        try:
            for job in fetch_feed(url):
                if job["id"] in existing:
                    index = next(index for index, current in enumerate(state["opportunities"]) if current["id"] == job["id"])
                    state["opportunities"][index] = {**existing[job["id"]], **job}
                    refreshed += 1
                else:
                    state["opportunities"].insert(0, job)
                    existing[job["id"]] = job
                    fetched += 1
        except Exception as error:
            failures.append({"url": url, "error": str(error)})
    state["opportunities"] = sorted(state["opportunities"], key=lambda job: (job.get("match_score", 0), job.get("published_at", "")), reverse=True)
    run = {"id": f"opportunity-run-{len(state['runs']) + 1:03d}", "completed_at": now_iso(), "feeds": feeds, "fetched": fetched, "refreshed": refreshed, "failures": failures, "mode": "public_sources"}
    state["runs"].insert(0, run)
    state["updated_at"] = run["completed_at"]
    return run


def preparation_for(job: dict) -> dict:
    title = job.get("title", "this internship")
    description = job.get("description", "")
    skills = job.get("matched_skills", [])
    return {
        "job_id": job["id"],
        "title": title,
        "source": job.get("source", "job source"),
        "technical_questions": [
            f"How would you troubleshoot a production issue relevant to {title}, and which logs, metrics, or traces would you inspect first?",
            f"Which part of your background with {', '.join(skills[:3]) or 'automation and cloud systems'} best demonstrates readiness for this role?",
        ],
        "coding_exercise": "Write a small Python or shell utility that reads service events, groups failures by reason, and reports the top three actionable patterns. Explain how you would test it.",
        "interview_scenario": f"You are supporting a service related to {title}. A deployment increases error rates and customer tickets at the same time. Walk through containment, communication, diagnosis, rollback, and follow-up.",
        "learning_plan": [
            f"Review the role description and map each requirement to one concrete project or work example.",
            "Practice one timed troubleshooting explanation using an incident from your resume.",
            "Complete the coding exercise and add tests for malformed input and repeated events.",
        ],
        "description_basis": description[:400],
    }


def evaluate_response(prompt: str, answer: str) -> dict:
    text = clean_text(answer).lower()
    signals = {
        "diagnosis": any(token in text for token in ("log", "metric", "trace", "reproduce", "hypothesis")),
        "safety": any(token in text for token in ("rollback", "mitigate", "contain", "blast radius", "fallback")),
        "communication": any(token in text for token in ("customer", "stakeholder", "owner", "document", "timeline")),
        "validation": any(token in text for token in ("test", "monitor", "alert", "assert", "edge case")),
    }
    score = min(100, sum(signals.values()) * 20 + min(20, len(text) // 80 * 5))
    return {"score": score, "signals": signals, "feedback": "Strong, structured response." if score >= 75 else "Add concrete evidence, a safety step, and how you would validate the result."}


def dashboard(state: dict) -> dict:
    jobs = state.get("opportunities", [])
    selected = next((job for job in jobs if job["id"] == state.get("selected_id")), None)
    return {
        "opportunities": jobs[:30],
        "selected": selected,
        "target_roles": TARGET_ROLES,
        "configured_sources": configured_feeds(),
        "source_status": "configured" if configured_feeds() else "needs_source_configuration",
        "last_scan": state["runs"][0] if state.get("runs") else None,
        "prep": preparation_for(selected) if selected else None,
        "activities": state.get("activities", [])[-20:],
        "progress": {"applications": sum(1 for job in jobs if job.get("status") == "applied"), "saved": sum(1 for job in jobs if job.get("status") == "saved"), "prep_sessions": len(state.get("activities", []))},
    }
