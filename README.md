# OSINT Report — Italian Information Ecosystem on X During the Iran–USA/Israel Conflict

## Overview
Computational analysis of the Italian information ecosystem on X (formerly Twitter) in the ten days following the outbreak of the Iran–USA/Israel conflict (February 28 – March 10, 2026).

## Methodology

**Level 1 — Narrative Analysis**
- Custom scraper built with Playwright to collect 3,631 Top Tweets in Italian
- Temporal windows of 8 hours converted to UNIX timestamps for precise querying
- Two-phase analysis: hashtag frequency, semantic bigrams, engagement metrics, dominant actors

**Level 2 — Network Analysis**
- Directed graph construction with NetworkX
- Fruchterman-Reingold spatial layout
- Community detection with Louvain algorithm

## Key Results
- Network modularity: **Q = 0.97** (106 communities, 306 nodes)
- Internal density: **100%** for all major clusters
- Phase 1 (Shock): 2,386 tweets, 165,043 interactions
- Phase 2 (Consolidation): 1,245 tweets, 217,016 interactions
- Identification of the **second screen effect** as amplification mechanism

## Tech Stack
- Python (pandas, NetworkX, Matplotlib, Playwright)
- Data export: CSV with permalink traceability

## Contents
- `osint_report.pdf` — Full report (Italian)
- `scraper/` — Playwright scraper script
- `analysis/` — Network analysis notebooks
