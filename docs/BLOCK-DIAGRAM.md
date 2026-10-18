# Lineage platform: block diagram

Companion to [PLATFORM-ARCHITECTURE.md](PLATFORM-ARCHITECTURE.md), [VERCEL-MIGRATION.md](VERCEL-MIGRATION.md) and
[BUILD-PLAN.md](BUILD-PLAN.md).

```
┌───────────────────────────────────────────────────────────────────────────┐
│                               TRIGGERS                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ New email    │  │ File upload  │  │ Hourly cron  │  │ Archivist    │   │
│  │ (Gmail)      │  │              │  │ (due work)   │  │ clicks "run" │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└──────────────────────────────────────┬────────────────────────────────────┘
                                       ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         CREDITS CHECK                                     │
│        enough Lineage Credits?  ── no ──►  stop + "top up" task            │
└──────────────────────────────────────┬────────────────────────────────────┘
                                       ▼ yes
┌───────────────────────────────────────────────────────────────────────────┐
│                    WORKFLOWS  (durable, sleeps for free)                  │
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │                 CORE RESEARCH AGENT (eve)                       │     │
│   └───────────────────────────────┬─────────────────────────────────┘     │
│                                   ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │                       SKILL GALLERY                             │     │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │     │
│   │  │ Reply    │ │ Web      │ │ Request  │ │ Article  │ │ Fact   │ │     │
│   │  │ reader   │ │ research │ │ writer   │ │ writer   │ │ checker│ │     │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │     │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │     │
│   │  │ Chapter  │ │ Book     │ │ Clip     │ │Newsletter│ │ ...    │ │     │
│   │  │ writer   │ │ writer   │ │ generator│ │ writer   │ │        │ │     │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │     │
│   │        (each skill: versioned, with its own evals)               │     │
│   └─────────────────────────────────────────────────────────────────┘     │
└───────┬────────────────────────┬──────────────────────────┬───────────────┘
        ▼                        ▼                          ▼
┌───────────────┐   ┌────────────────────────┐   ┌────────────────────────┐
│  AI GATEWAY   │   │       APPROVALS        │   │       SANDBOX          │
│ cheap model / │   │  Archivist approves    │   │  book build, OCR       │
│ good model    │   │  sends + changes       │   │  (only when needed)    │
│ (swap anytime)│   └───────────┬────────────┘   └────────────────────────┘
└───────────────┘               ▼
                    ┌────────────────────────┐
                    │        PUBLISH         │
                    │  rebuild what changed  │
                    └───────────┬────────────┘
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐   ┌────────────────────────┐   ┌────────────────────────┐
│ LINEAGE SITES │   │     UPDATES FEED       │   │   EMAIL DIGEST         │
│ one per family│   │  what's new            │   │  to subscribers        │
└───────────────┘   └────────────────────────┘   └────────────────────────┘


┌───────────────────────────────────────────────────────────────────────────┐
│                               STORAGE                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Database     │  │ Vercel Blob  │◄►│ Google Drive │  │ GitHub       │   │
│  │ (Neon)       │  │ (files)      │  │ (mirror copy)│  │ (book text)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│                         ARCHIVIST DASHBOARD                               │
│ Agents & runs │ Approvals │ Skills │ Credits & schedules │ Models │ Sites │
└───────────────────────────────────────────────────────────────────────────┘
```

**Flow:** something triggers a run → credits are checked → the core agent picks skills from the gallery → models are
called through AI Gateway → anything outward or any change to the book waits for the archivist → approved work is
published to the family's site, the updates feed and the email digest. Storage and the dashboard sit underneath.
