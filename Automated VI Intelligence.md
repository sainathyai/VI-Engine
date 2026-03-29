# Automated Vertical Intelligence Engine — Implementation Plan

## Project Summary

A multi-domain AI pipeline that discovers niche market signals, extracts clean content, filters and synthesizes with LLMs, stages for human review, and publishes to monetized sites. Revenue streams: AdSense → Mediavine → Paid subscriptions → B2B API feeds.

---

## Domain Selection (Required Before Phase 1 Starts)

Choose one domain to validate the pipeline before scaling. Criteria:

| Domain | Data Availability | Monetization Speed | Audience Size |
|---|---|---|---|
| Insurance & Capital Management | High (SEC, regulatory feeds) | Medium | Mid-market |
| Energy & Seismic Infrastructure | Medium (EDGAR permits, USGS) | Slow | Niche/B2B |
| Fintech & Compliance | High (regulatory APIs, news feeds) | Fast | Large |

**Recommendation:** Fintech & Compliance for fastest path to 10k pageviews. Insurance is strongest for B2B API revenue long-term.

---

## Tech Stack

| Layer | Tool | Cost |
|---|---|---|
| Scheduler | GCP Cloud Scheduler | Free |
| Compute | GCP Cloud Run | Free tier |
| Data Lake | GCP Cloud Storage | 5GB free |
| Staging DB | GCP Firestore | 1GB free |
| Extraction | Jina Reader (`r.jina.ai`) | Free tier |
| Filter LLM | Claude Haiku (API) | ~$0.001/call |
| Synthesis LLM | Claude Sonnet (API) | ~$0.01/article |
| CMS | WordPress or Ghost | $0–$9/mo |
| Hosting/CDN | Cloudflare Pages | Free |
| Dev Tooling | Claude Code (Pro plan) | $17/mo |

**Estimated running cost at MVP scale:** $20–40/mo total (API + hosting)

---

## Phase 1 — Validate the Pipeline Locally (Weeks 1–3)

**Goal:** Prove end-to-end quality before touching cloud infrastructure.

**Tasks:**
- Pick one domain (see table above)
- Identify 3–5 high-signal data sources (RSS feeds, SEC EDGAR endpoints, subreddits)
- Write discovery script to pull URLs on a schedule
- Pass URLs through Jina Reader to get clean Markdown
- Write filter prompt (Haiku): keep or discard based on signal criteria
- Write synthesis prompt (Sonnet): produce structured analysis with SEO headers and citations
- Save output as local `.md` files
- Manually review 10 outputs and tune prompts until quality is consistent

**Exit Criteria:** 10 consecutive articles pass manual review without major edits.

---

## Phase 2 — Quality Gate + CMS Publishing (Weeks 4–5)

**Goal:** Automate staging and enable daily human review workflow.

**Tasks:**
- Set up Firestore to store finalized drafts with metadata (source URLs, timestamp, domain tag)
- Build a simple review dashboard (or use Firestore console) for the 10-min daily review
- Configure WordPress or Ghost with REST API access
- Write webhook script: approved draft in Firestore → publish to CMS
- Set up basic SEO (Yoast or RankMath on WordPress)
- Apply for Google AdSense

**Exit Criteria:** First 5 articles live on site, AdSense application submitted.

---

## Phase 3 — Move to GCP + Automate (Weeks 6–7)

**Goal:** Remove manual pipeline execution, run fully on schedule.

**Tasks:**
- Containerize all Python scripts with Docker
- Deploy containers to GCP Cloud Run
- Wire GCP Cloud Scheduler to trigger pipeline every 6 hours
- Set up GCP Cloud Storage as Data Lake for raw JSON/Markdown history
- Add deduplication logic (don't re-process already-seen URLs)
- Set up basic error alerting (GCP Cloud Logging → email alert)

**Exit Criteria:** Pipeline runs for 7 consecutive days without manual intervention.

---

## Phase 4 — Monetization Scaling (Weeks 8+)

**Goal:** Grow traffic and unlock higher-yield revenue channels.

**Milestones:**

- **1,000 pageviews/mo** — AdSense live, first ad revenue
- **10,000 pageviews/mo** — Apply to Mediavine or Raptive (3–5x RPM improvement)
- **500 email subscribers** — Launch Substack or Ghost freemium tier
- **Paid tier launch** — $20–50/mo for deep analysis access
- **B2B API packaging** — JSON feed sold to brokerages or logistics firms

---

## Development Tooling Setup

- **VS Code** — file editing, viewing, Git management
- **Claude Code** (terminal) — agentic pipeline development, script iteration, debugging
- **Claude.ai Pro** — research, prompt engineering, planning
- **Anthropic Console** — separate API account for pipeline LLM calls (billed per token)

> Note: Pro plan ($17/mo) covers development. API credits are separate and billed by usage when the pipeline runs in production.

---

## Risk & Mitigation

| Risk | Mitigation |
|---|---|
| LLM output quality inconsistent | Tune filter + synthesis prompts in Phase 1 before automating |
| Jina/Firecrawl rate limits | Cache raw Markdown in GCS, avoid re-fetching same URLs |
| AdSense rejection | Ensure 10+ quality articles live before applying |
| GCP free tier exceeded | Monitor Cloud Run invocations; pipeline runs 4x/day = well within limits |
| Domain chosen has thin data | Switch domains early — pipeline is domain-agnostic |

---

## Next Actions

- [ ] Select target domain
- [ ] Identify 3–5 data sources for that domain
- [ ] Set up Anthropic Console account for API access
- [ ] Install Claude Code
- [ ] Begin Phase 1 discovery script