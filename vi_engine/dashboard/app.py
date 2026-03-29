"""FastAPI dashboard — 3-stage newsletter review workflow.

Stage 1: Review discovered topics → approve / discard
Stage 2: Generate newsletter from approved topics
Stage 3: Approve newsletter for publishing to selected platforms
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import markdown as md_lib
from fastapi import FastAPI, Form, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from vi_engine.config import (
    DOMAIN_TAG,
    NEWSLETTER_DIR,
    SCHEDULER_SECRET,
    STATE_DB,
    SUBSTACK_DRAFTS_DIR,
    SUBSTACK_POSTS_DIR,
)
from vi_engine.publishers import get_publisher
from vi_engine.categorize import classify_by_llm
from vi_engine.extract import fetch_markdown, fetch_snippet
from vi_engine.llm import generate_platform_content, generate_preview, get_client, synthesize_article
from vi_engine.skills import build_system_prompt, list_industries, list_voices
from vi_engine.skills.loader import PLATFORMS as SKILL_PLATFORMS
from vi_engine.pipeline_config import pipeline_labels
from vi_engine.state import (
    add_publish_target,
    candidate_counts,
    candidate_filter_options,
    create_newsletter,
    get_candidate,
    get_newsletter,
    get_newsletter_candidates,
    init_db,
    list_candidates,
    list_newsletters,
    list_publish_targets,
    set_candidate_description,
    set_candidate_output,
    set_candidate_status,
    set_candidate_summary,
    set_candidate_tags,
    set_newsletter_skills,
    set_newsletter_status,
    set_publish_target_status,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="VI Engine Dashboard")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Clean stored descriptions at render time (strips emails, social links, nav junk)
from vi_engine.extract import _clean_snippet
templates.env.filters["clean_preview"] = lambda text, max_chars=400: _clean_snippet(str(text or ""), max_chars=max_chars)


@app.on_event("startup")
def _startup() -> None:
    init_db(STATE_DB)
    NEWSLETTER_DIR.mkdir(parents=True, exist_ok=True)
    SUBSTACK_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    SUBSTACK_POSTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Helpers ───────────────────────────────────────────────

def _slug(s: str, max_len: int = 60) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len] or "post"


def _extract_title(md: str) -> str:
    for line in (md or "").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return "Untitled"


# ─── Stage 1: Topic Review ────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    counts = candidate_counts(STATE_DB)
    newsletters = list_newsletters(STATE_DB, limit=5)
    return templates.TemplateResponse(request, "index.html", {
        "counts": counts,
        "newsletters": newsletters,
        "domain": DOMAIN_TAG,
    })


@app.get("/topics", response_class=HTMLResponse)
async def topics(
    request: Request,
    status: str = Query("discovered"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str = Query(""),
    source: str = Query(""),
    pipeline: str = Query(""),
    sort_by: str = Query("score"),
):
    offset_count = (page - 1) * page_size
    candidates = list_candidates(
        STATE_DB,
        status=status,
        limit=page_size + offset_count + 1,
        category=category or None,
        source=source or None,
        pipeline=pipeline or None,
        sort_by=sort_by,
    )
    page_items = candidates[offset_count : offset_count + page_size]
    has_next = len(candidates) > offset_count + page_size
    filter_opts = candidate_filter_options(STATE_DB)
    pl_labels = pipeline_labels()
    return templates.TemplateResponse(request, "topics.html", {
        "candidates": page_items,
        "status": status,
        "page": page,
        "has_next": has_next,
        "page_size": page_size,
        "domain": DOMAIN_TAG,
        "category": category,
        "source": source,
        "sort_by": sort_by,
        "filter_categories": filter_opts["categories"],
        "filter_sources": filter_opts["sources"],
        "filter_pipelines": filter_opts["pipelines"],
        "pipeline": pipeline,
        "pipeline_labels": pl_labels,
    })


@app.post("/topics/approve")
async def approve_topics(candidate_ids: str = Form(...)):
    ids = [int(x.strip()) for x in candidate_ids.split(",") if x.strip().isdigit()]
    for cid in ids:
        set_candidate_status(STATE_DB, candidate_id=cid, status="approved", note="approved via dashboard")
    return RedirectResponse("/topics?status=approved", status_code=303)


@app.post("/topics/discard")
async def discard_topics(candidate_ids: str = Form(...)):
    ids = [int(x.strip()) for x in candidate_ids.split(",") if x.strip().isdigit()]
    for cid in ids:
        set_candidate_status(STATE_DB, candidate_id=cid, status="discarded", note="discarded via dashboard")
    return RedirectResponse("/topics", status_code=303)


@app.post("/topics/{candidate_id}/approve")
async def approve_single(candidate_id: int):
    set_candidate_status(STATE_DB, candidate_id=candidate_id, status="approved", note="approved via dashboard")
    return RedirectResponse("/topics", status_code=303)


@app.post("/topics/{candidate_id}/discard")
async def discard_single(candidate_id: int):
    set_candidate_status(STATE_DB, candidate_id=candidate_id, status="discarded", note="discarded via dashboard")
    return RedirectResponse("/topics", status_code=303)


@app.post("/api/topics/{candidate_id}/snippet")
async def fetch_snippet_single(candidate_id: int):
    """Fetch a short text snippet from the page (no LLM). Returns JSON."""
    cand = get_candidate(STATE_DB, candidate_id=candidate_id)
    if not cand or not cand.get("url"):
        return JSONResponse({"ok": False, "error": "Candidate not found"}, status_code=404)
    try:
        snippet = fetch_snippet(cand["url"])
        if snippet:
            set_candidate_description(STATE_DB, candidate_id=candidate_id, description=snippet)
        return JSONResponse({"ok": True, "description": snippet})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.post("/api/topics/{candidate_id}/enrich")
async def enrich_single(candidate_id: int):
    """Fetch page content via Jina and generate an AI preview summary. Returns JSON."""
    cand = get_candidate(STATE_DB, candidate_id=candidate_id)
    if not cand or not cand.get("url"):
        return JSONResponse({"ok": False, "error": "Candidate not found"}, status_code=404)
    try:
        md = fetch_markdown(cand["url"])
        client = get_client()
        summary = generate_preview(client, md)
        set_candidate_summary(STATE_DB, candidate_id=candidate_id, summary=summary)
        # Also classify via LLM
        category, content_type = classify_by_llm(client, cand.get("title", ""), summary)
        if category or content_type:
            set_candidate_tags(STATE_DB, candidate_id=candidate_id, category=category, content_type=content_type)
        return JSONResponse({"ok": True, "summary": summary, "category": category, "content_type": content_type})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.post("/api/topics/enrich-bulk")
async def enrich_bulk(candidate_ids: str = Form(...)):
    """Bulk enrich: returns JSON with results per candidate."""
    ids = [int(x.strip()) for x in candidate_ids.split(",") if x.strip().isdigit()]
    client = get_client()
    results: dict[int, dict] = {}
    for cid in ids:
        cand = get_candidate(STATE_DB, candidate_id=cid)
        if not cand or not cand.get("url"):
            results[cid] = {"ok": False, "error": "not found"}
            continue
        if cand.get("summary"):
            results[cid] = {"ok": True, "summary": cand["summary"], "cached": True}
            continue
        try:
            md = fetch_markdown(cand["url"])
            summary = generate_preview(client, md)
            set_candidate_summary(STATE_DB, candidate_id=cid, summary=summary)
            results[cid] = {"ok": True, "summary": summary}
        except Exception as exc:
            results[cid] = {"ok": False, "error": str(exc)}
    return JSONResponse({"ok": True, "results": {str(k): v for k, v in results.items()}})


# ─── Stage 2: Generate Newsletter ─────────────────────────

@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    approved = list_candidates(STATE_DB, status="approved", limit=50)
    summarized = list_candidates(STATE_DB, status="summarized", limit=50)
    return templates.TemplateResponse(request, "generate.html", {
        "approved": approved,
        "summarized": summarized,
        "domain": DOMAIN_TAG,
    })


@app.post("/generate/summarize")
async def summarize_approved(candidate_ids: str = Form(...)):
    """Fetch content + LLM synthesis for each approved candidate."""
    ids = [int(x.strip()) for x in candidate_ids.split(",") if x.strip().isdigit()]
    client = get_client()

    for cid in ids:
        cand = get_candidate(STATE_DB, candidate_id=cid)
        if not cand or cand.get("status") != "approved":
            continue
        try:
            md = fetch_markdown(cand["url"])
            article = synthesize_article(client, cand["url"], md)
        except Exception:
            continue

        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        post_dir = SUBSTACK_POSTS_DIR / ts
        post_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{_slug(cand.get('title', ''))}.md"
        post_path = post_dir / fname

        header = f"<!-- domain:{DOMAIN_TAG} source:{cand['url']} -->\n\n"
        post_path.write_text(header + article.strip() + "\n", encoding="utf-8")
        set_candidate_output(STATE_DB, candidate_id=cid, output_path=str(post_path), status="summarized")

    return RedirectResponse("/generate", status_code=303)


@app.post("/generate/newsletter")
async def compile_newsletter(candidate_ids: str = Form(...), title: str = Form("")):
    """Compile selected summarized candidates into a newsletter draft."""
    ids = [int(x.strip()) for x in candidate_ids.split(",") if x.strip().isdigit()]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nl_title = title.strip() or f"Newsletter Draft — {today}"

    parts: list[str] = [f"# {nl_title}", "", f"Domain: {DOMAIN_TAG}", "", "## Top Signals", ""]

    for cid in ids:
        cand = get_candidate(STATE_DB, candidate_id=cid)
        if not cand:
            continue
        post_path = Path(cand.get("output_path") or "")
        post_md = post_path.read_text(encoding="utf-8") if post_path.exists() else ""
        c_title = cand.get("title") or _extract_title(post_md)
        parts.append(f"### {c_title}")
        parts.append("")
        body_lines = [ln for ln in post_md.splitlines() if not ln.startswith("<!-- ") and not ln.startswith("# ")]
        parts.append("\n".join(body_lines).strip() or "_(content pending)_")
        parts.append("")

    body = "\n".join(parts)

    draft_path = SUBSTACK_DRAFTS_DIR / f"draft_{today.replace('-', '')}.md"
    draft_path.write_text(body + "\n", encoding="utf-8")

    nl_id = create_newsletter(STATE_DB, title=nl_title, body=body, candidate_ids=ids, output_path=str(draft_path))
    return RedirectResponse(f"/newsletters/{nl_id}", status_code=303)


# ─── Stage 3: Publish Gate ─────────────────────────────────

PLATFORMS = ["substack", "ghost", "wordpress", "medium", "linkedin", "twitter"]


@app.get("/newsletters", response_class=HTMLResponse)
async def newsletters_list(request: Request):
    newsletters = list_newsletters(STATE_DB, limit=50)
    return templates.TemplateResponse(request, "newsletters.html", {
        "newsletters": newsletters,
        "domain": DOMAIN_TAG,
    })


@app.get("/newsletters/{newsletter_id}", response_class=HTMLResponse)
async def newsletter_detail(request: Request, newsletter_id: int):
    nl = get_newsletter(STATE_DB, newsletter_id=newsletter_id)
    if not nl:
        return RedirectResponse("/newsletters", status_code=303)
    items = get_newsletter_candidates(STATE_DB, newsletter_id=newsletter_id)
    targets = list_publish_targets(STATE_DB, newsletter_id=newsletter_id)
    return templates.TemplateResponse(request, "newsletter_detail.html", {
        "newsletter": nl,
        "items": items,
        "targets": targets,
        "platforms": PLATFORMS,
        "domain": DOMAIN_TAG,
        "voices": list_voices(),
        "industries": list_industries(),
        "preview_platforms": list(SKILL_PLATFORMS.keys()),
    })


@app.post("/newsletters/{newsletter_id}/skills")
async def update_newsletter_skills(newsletter_id: int, voice: str = Form(""), industry: str = Form("")):
    """Save the editorial voice and industry for a newsletter."""
    set_newsletter_skills(STATE_DB, newsletter_id=newsletter_id, voice=voice, industry=industry)
    return RedirectResponse(f"/newsletters/{newsletter_id}", status_code=303)


@app.post("/api/newsletters/{newsletter_id}/preview/{platform}")
async def generate_preview_for_platform(newsletter_id: int, platform: str):
    """Generate a platform-specific preview (blog/linkedin/twitter) using the skills system."""
    if platform not in SKILL_PLATFORMS:
        return JSONResponse({"ok": False, "error": f"Unknown platform: {platform}"}, status_code=400)

    nl = get_newsletter(STATE_DB, newsletter_id=newsletter_id)
    if not nl:
        return JSONResponse({"ok": False, "error": "Newsletter not found"}, status_code=404)

    try:
        client = get_client()
        content = generate_platform_content(
            client,
            source_content=nl.get("body", ""),
            platform=platform,
            voice=nl.get("voice") or None,
            industry=nl.get("industry") or None,
            title=nl.get("title", ""),
        )
        return JSONResponse({"ok": True, "platform": platform, "content": content})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.post("/newsletters/{newsletter_id}/publish")
async def set_publish_platforms(newsletter_id: int, platforms: str = Form("")):
    """Mark which platforms this newsletter should be published to."""
    selected = [p.strip() for p in platforms.split(",") if p.strip() in PLATFORMS]
    for platform in selected:
        add_publish_target(STATE_DB, newsletter_id=newsletter_id, platform=platform)
    if selected:
        set_newsletter_status(STATE_DB, newsletter_id=newsletter_id, status="queued")
    return RedirectResponse(f"/newsletters/{newsletter_id}", status_code=303)


@app.post("/newsletters/{newsletter_id}/approve-publish")
async def approve_publish(newsletter_id: int):
    """Final approval — push newsletter to all queued platforms, then mark published."""
    nl = get_newsletter(STATE_DB, newsletter_id=newsletter_id)
    if not nl:
        return RedirectResponse("/newsletters", status_code=303)

    title = nl.get("title", "Newsletter")
    body_md = nl.get("body", "")
    html = md_lib.markdown(body_md, extensions=["extra", "nl2br"])

    # Social platforms need platform-specific content generated by the skills system
    _SOCIAL_PLATFORMS = {"twitter"}

    targets = list_publish_targets(STATE_DB, newsletter_id=newsletter_id)
    for t in targets:
        if t["status"] != "pending":
            continue
        publisher = get_publisher(t["platform"])
        if publisher is None:
            set_publish_target_status(STATE_DB, target_id=t["id"], status="skipped")
            continue
        try:
            if t["platform"] in _SOCIAL_PLATFORMS:
                # Generate platform-specific content (thread/post format) via skills
                llm = get_client()
                content = generate_platform_content(
                    llm,
                    source_content=body_md,
                    platform=t["platform"],
                    voice=nl.get("voice") or "skeptical_analyst",
                    industry=nl.get("industry") or "tech",
                    title=title,
                )
                live_url = publisher.publish(title, content, tags=[DOMAIN_TAG])
            else:
                live_url = publisher.publish(title, html, tags=[DOMAIN_TAG])
            set_publish_target_status(
                STATE_DB, target_id=t["id"], status="published", publish_url=live_url
            )
        except Exception as exc:
            set_publish_target_status(
                STATE_DB, target_id=t["id"], status="failed",
                publish_url=f"error: {exc}",
            )

    set_newsletter_status(STATE_DB, newsletter_id=newsletter_id, status="published")
    return RedirectResponse(f"/newsletters/{newsletter_id}", status_code=303)


@app.post("/publish-targets/{target_id}/status")
async def update_target_status(target_id: int, status: str = Form(...), publish_url: str = Form("")):
    set_publish_target_status(STATE_DB, target_id=target_id, status=status, publish_url=publish_url)
    return RedirectResponse("/newsletters", status_code=303)


# ─── Phase 3: GCP Cloud Scheduler trigger ─────────────────────────────────

@app.post("/run/collect")
async def trigger_collect(x_scheduler_secret: str | None = Header(None)):
    """HTTP trigger for GCP Cloud Scheduler — runs the discovery pipeline.

    Cloud Scheduler config:
      URL:    https://<your-cloud-run-url>/run/collect
      Method: POST
      Headers: X-Scheduler-Secret: <SCHEDULER_SECRET>
    """
    if SCHEDULER_SECRET and x_scheduler_secret != SCHEDULER_SECRET:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=403)

    import argparse
    import threading

    from vi_engine.collect_candidates import collect

    def _run() -> None:
        args = argparse.Namespace(
            limit=50,
            rss_limit=10,
            gnews_limit=25,
        )
        collect(args)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return JSONResponse({"ok": True, "message": "Collection started in background"})
