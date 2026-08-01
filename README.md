# റേഷൻ ഉണ്ടോ? · RationUndo

> Track whether your Kerala ration shop (Fair Price Shop) has received its monthly stock allocation rice, wheat, sugar, kerosene, and more.
> Search by shop number, place name, or owner. Browse by district and taluk. Use GPS to find the nearest shops.
> Data scraped daily from the official [epos.kerala.gov.in](https://epos.kerala.gov.in) portal and served fast from a local database.

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat&logo=supabase&logoColor=white)
![HTMX](https://img.shields.io/badge/HTMX-36C?style=flat&logo=htmx&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=githubactions&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?style=flat&logo=render&logoColor=white)

</div>

![RationUndo app screenshot](docs/rationundo.png)

---

## How it works

```mermaid
flowchart LR
    A([epos.kerala.gov.in]) -->|daily scrape 2 AM IST| B[(PostgreSQL Supabase)]
    B -->|sub-200ms| C([FastAPI])
    C -->|HTMX fragments| D([Browser])

    style A fill:#e8f5e9,stroke:#2e7d32
    style B fill:#e3f2fd,stroke:#1565c0
    style C fill:#fff3e0,stroke:#e65100
    style D fill:#f3e5f5,stroke:#6a1b9a
```

A **GitHub Actions cron** scrapes the official ePOS portal once a day and stores every shop's stock status in PostgreSQL. User searches are served entirely from the local DB, no external calls at request time.

---

## Data flow

```mermaid
sequenceDiagram
    participant U as User
    participant SW as Service Worker
    participant API as FastAPI
    participant DB as PostgreSQL

    U->>SW: Open app / search shop
    SW->>API: GET /htmx/select?type=shop&id=...
    API->>DB: SELECT by ARD number
    DB-->>API: shop + stock rows
    API-->>SW: HTML fragment (Jinja2)
    SW-->>U: Rendered card (< 200ms)

    note over SW: Shell cached offline<br/>API always fresh
```

---

## Features

- Search by **shop number**, **place name**, or **owner name** (fuzzy `pg_trgm`)
- **Near me** GPS search, haversine distance sort
- Browse **District > Taluk > Shop**
- **Bookmark** favourite shops (localStorage)
- Per-commodity allocated vs received quantities
- **Share** shop link via native share / WhatsApp
- **PWA** installable, offline shell via service worker
- Malayalam-first UI

Covers **14 districts · 14,000+ shops · 5,000+ pincodes** across Kerala.

---

> Data sourced from the public [epos.kerala.gov.in](https://epos.kerala.gov.in) portal.
> Not affiliated with the Government of Kerala.

<div align="center">

[![MIT License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE) © 2026 Jithin

</div>
