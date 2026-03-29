"""Local Daily Review Dashboard (CLI).

This is the human-in-the-loop gate: it shows discovered candidates and only
calls the synthesis LLM after you approve an item.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from vi_engine.config import (
    DEFAULT_PAGE_SIZE,
    DOMAIN_TAG,
    NEWSLETTER_DIR,
    SUBSTACK_DRAFTS_DIR,
    SUBSTACK_POSTS_DIR,
    STATE_DB,
)
from vi_engine.extract import fetch_markdown
from vi_engine.llm import get_client, synthesize_article
from vi_engine.state import get_candidate, init_db, list_candidates, set_candidate_output, set_candidate_status


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _slug(s: str, max_len: int = 60) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len] or "post"


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


def _extract_title_from_markdown(markdown: str) -> str:
    for line in (markdown or "").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return "Untitled"


def _compile_newsletter_draft(*, included_candidate_ids: Iterable[int] = ()) -> Path:
    SUBSTACK_POSTS_DIR.mkdir(parents=True, exist_ok=True)
    SUBSTACK_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    included_set = set(included_candidate_ids)
    # Draft candidates: take last summarized items; if you provided ids, only include those.
    candidates = list_candidates(STATE_DB, status="summarized", limit=25)
    selected = [c for c in candidates if not included_set or c["id"] in included_set]
    selected = selected[:10]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    draft_path = SUBSTACK_DRAFTS_DIR / f"draft_{today.replace('-', '')}.md"

    parts: list[str] = []
    parts.append(f"# Tech Newsletter Draft ({today})")
    parts.append("")
    parts.append(f"Domain: {DOMAIN_TAG}")
    parts.append("")
    if not selected:
        parts.append("_No approved items to compile yet._")
        draft_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
        return draft_path

    parts.append("## Top Signals")
    parts.append("")

    for c in selected:
        post_path = Path(c.get("output_path") or "")
        post_md = post_path.read_text(encoding="utf-8") if post_path.exists() else ""
        title = c.get("title") or _extract_title_from_markdown(post_md)
        parts.append(f"### {title}")
        parts.append("")
        # Avoid repeating the H1 if present.
        post_body = "\n".join([ln for ln in (post_md or "").splitlines() if not ln.startswith("# ") or ln.strip() == "#"])
        parts.append(post_body.strip() or "_(missing content)_")
        parts.append("")

    draft_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return draft_path


def _summarize_candidate(candidate: dict, client) -> str:
    # Fetch content only after approval, keeping LLM summarization strictly gated.
    markdown = fetch_markdown(candidate["url"])
    return synthesize_article(client, candidate["url"], markdown)


def _write_post(markdown: str, *, url: str) -> tuple[Path, str]:
    title = _extract_title_from_markdown(markdown)
    date_folder = _utc_stamp()
    post_dir = SUBSTACK_POSTS_DIR / date_folder
    post_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{_slug(title)}.md"
    path = post_dir / fname

    header = f"<!-- domain:{DOMAIN_TAG} source:{url} -->\n\n"
    path.write_text(header + markdown.strip() + "\n", encoding="utf-8")
    return path, title


def parse_ids(s: str) -> list[int]:
    s = s.strip()
    if not s:
        return []
    parts = re.split(r"[,\s]+", s)
    out: list[int] = []
    for p in parts:
        if not p:
            continue
        out.append(int(p))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Local daily review dashboard (approve/discard before summarization).")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max", type=int, default=0, help="Optional cap on number of approvals to process in this run.")
    args = parser.parse_args()

    init_db(STATE_DB)

    approved_ids: list[int] = []
    processed = 0

    while True:
        candidates = list_candidates(STATE_DB, status="discovered", limit=args.page_size)
        if not candidates:
            print("No discovered candidates found. Collect more with `collect_candidates.py`.")
            break

        print("\nDiscovered Candidates:")
        for c in candidates:
            print(f"- id={c['id']} source={c['source']} pub={c['pub_date'] or ''}")
            print(f"  title={c['title']}")
            if c.get("url"):
                print(f"  url={c['url']}")

        inp = input("\nCommand: `a <ids>` approve, `d <ids>` discard, `p` compile draft, `q` quit\n> ").strip().lower()
        if inp in {"q", "quit", "exit"}:
            break
        if inp in {"p", "print"}:
            draft = _compile_newsletter_draft(included_candidate_ids=approved_ids)
            print(f"Draft compiled: {draft}")
            continue
        if inp.startswith("a "):
            if args.max and processed >= args.max:
                print("Max approvals reached for this run.")
                break
            ids = parse_ids(inp[2:])
            if not ids:
                continue
            client = get_client()

            for cid in ids:
                if args.max and processed >= args.max:
                    break
                cand = get_candidate(STATE_DB, candidate_id=cid)
                if not cand:
                    print(f"Skipping missing candidate id={cid}")
                    continue
                if cand.get("status") != "discovered":
                    print(f"Skipping candidate id={cid} (status={cand.get('status')})")
                    continue
                print(f"\nApproving id={cid}: {cand.get('title')}")
                # LLM summarization occurs only after explicit approval.
                synthesized = _summarize_candidate(cand, client)
                post_path, _ = _write_post(synthesized, url=cand.get("url") or "")
                set_candidate_output(STATE_DB, candidate_id=cid, output_path=str(post_path), status="summarized")
                approved_ids.append(cid)
                processed += 1
                print(f"Summarized → {post_path}")

            draft = _compile_newsletter_draft(included_candidate_ids=approved_ids)
            print(f"Draft updated: {draft}")
            continue
        if inp.startswith("d "):
            ids = parse_ids(inp[2:])
            if not ids:
                continue
            for cid in ids:
                cand = get_candidate(STATE_DB, candidate_id=cid)
                if not cand:
                    continue
                if cand.get("status") != "discovered":
                    continue
                set_candidate_status(STATE_DB, candidate_id=cid, status="discarded", note="discarded via dashboard")
            print("Discarded selected items.")
            continue

        print("Unrecognized command.")

    # Final compile on exit if anything was approved.
    if approved_ids:
        draft = _compile_newsletter_draft(included_candidate_ids=approved_ids)
        print(f"Final draft compiled: {draft}")


if __name__ == "__main__":
    main()

