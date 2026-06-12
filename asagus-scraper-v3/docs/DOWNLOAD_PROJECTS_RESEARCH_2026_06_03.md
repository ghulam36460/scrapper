# Download Projects Research - 2026-06-03

This is the one-time local audit of projects found under `Download/` and how their strongest ideas were integrated into ASAGUS.

## Integration Policy

- Prefer native ASAGUS glue and optional adapters over copying whole projects.
- Use permissive-code ideas directly only when the license is clear from the local manifest.
- Treat AGPL projects as reference architecture or optional external services unless the whole ASAGUS distribution is intentionally relicensed.
- Keep network scraping gated by ASAGUS runtime controls, robots handling, pacing, and manual review for access challenges.

## Project Findings

| Project | Local Signal | Strongest Part | ASAGUS Integration |
| --- | --- | --- | --- |
| `Scrapy` | `pyproject.toml` says BSD-3-Clause | Mature selector/parsel ecosystem and crawler hygiene | Optional Scrapy/parsel selector adapter in `external_adapters.py`; extraction cascade can use it when installed. |
| `Scrapling` | `pyproject.toml` uses LICENSE file and BSD classifier | Adaptive parser, DOM recovery, static fetch fallback | Optional Scrapling parser/fetch adapters; ASAGUS keeps its own policy/compliance boundaries. |
| `Scrapegraph-ai` | README says MIT | Prompt-driven graph extraction and LLM fallback pattern | Kept as adapter-ready due heavy LangChain/Playwright dependency; ASAGUS LLM extraction remains provider-neutral. |
| `Agent-Reach` | `pyproject.toml` says MIT | Channel doctor pattern for RSS, YouTube, GitHub, social channels | Platform channel doctor added to external adapter state. |
| `firecrawl-main` | SDK folders have their own licenses; upstream core is advertised as open source and has AGPL risk | Hosted/API markdown scrape, search, batch scrape | Adapter-ready only; no core code copied. Use `FIRECRAWL_API_KEY` gating if a future hosted adapter is enabled. |
| `maxun-develop` | `package.json` says AGPL-3.0-or-later | No-code robot model, scheduling, recorder concept | Reference only; no source copied. Useful future direction for ASAGUS recipe recorder. |
| `scrapping-tool-of-maps-main` | Local app, no root license found | Maps lead enrichment, email/WhatsApp extraction, CAPTCHA stop behavior | Existing ASAGUS extraction/enrichment mirrors the safe parts: contact paths, WhatsApp normalization, challenge detection, no bypass. |
| `scrapping-for-outreach-tool-main` | Local app, no root license found | Same maps-to-leads workflow | Folded into ASAGUS discovery/extraction patterns, not copied wholesale. |
| `whatsapp-number-detector-main` | `package.json` has no license field | CSV phone/WhatsApp normalization and WA link readiness | ASAGUS enrichment emits `wa_link`, `whatsapp_status`, and `whatsapp_valid`. |
| `outreach-system-main` / `outreach-main` | Local lead/outreach tools, mixed/no clear root license | Lead scoring, segmenting, deliverability/spam heuristics, warmup concepts | New native `outreach_intelligence.py` adds fit score, segment, niche, recommended channel, and public-presence reasons. |

## Implemented In This Pass

- Added `asagus.layers.outreach_intelligence` for outreach fit scoring.
- Added enrichment metadata: `outreach_profile`, `outreach_fit_score`, `outreach_segment`, `outreach_niche`, and `recommended_outreach_channel`.
- Added analytics summary for outreach segments, recommended channels, niches, and average fit score.
- Added UI record-table badges for fit score, segment, and recommended channel.
- Added regression tests for outreach scoring and enrichment persistence.

