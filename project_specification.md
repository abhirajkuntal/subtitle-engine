# Project Specification: Multilingual Contextual Subtitle Engine (Algorithmic Word Alignment)

## 1. Project Overview
A professional-grade Manifest V3 browser extension designed to overlay synchronized, dual-language subtitles (English and Japanese) on media players (starting with YouTube). Rather than generic POS color-coding, the system executes **deterministic cross-lingual word alignment**: identical semantic words in both Japanese and English are rendered in matching distinct colors so learners can instantly map Japanese vocabulary to English equivalents. It extracts captions/transcripts, performs local dictionary-backed bipartite token alignment, and lets users save new vocabulary directly to a cloud database with video timestamps.

## 2. Tech Stack & Environment
*   **Frontend (Extension):** JavaScript / TypeScript, HTML5, CSS (Shadow DOM for style isolation).
*   **Backend (Microservice):** Python 3, FastAPI, Uvicorn.
*   **NLP & Morphological Processing:**
    *   `SudachiPy` + `sudachidict_core` (Japanese tokenization, lemma extraction).
    *   `jaconv` (Katakana to Hiragana reading conversion, particle pronunciation normalization).
    *   `spaCy` (`en_core_web_sm`) (English tokenization, lemmatization, POS tagging).
    *   `jamdict` / local SQLite JMDict (local dictionary gloss lookup for zero-latency, zero-cost word matching).
*   **Alignment Engine:**
    *   Custom deterministic bipartite / greedy overlap matcher: matches English token lemmas against Japanese JMDict glosses.
    *   Dynamic color-palette assignment: matched pairs share identical hex codes; unmapped particles/fillers receive neutral styling.
*   **Database & Auth:** Supabase (Managed PostgreSQL).
*   **Infrastructure & CI/CD:** GitHub Actions (`ci.yml` for automated linting with flake8/black and pytest), Docker, Render/Railway.
*   **Development Setup:**
    *   Virtual environment and dependencies managed via `uv`.
    *   Neovim with LSP + `nvim-tree` on Arch Linux.

## 3. System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        BROWSER (Client Side)                           │
│                                                                        │
│  YouTube Video Player                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Dual-Language Subtitle Overlay (Shadow DOM)                      │  │
│  │  • JP: [私(#3B82F6)] [は(#9CA)] [アニメ(#EF4444)] [を] [見ます(#10B)]│  │
│  │  • EN: [I(#3B82F6)] [watch(#10B)] [anime(#EF4444)]               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│              ▲                                                         │
│              │ DOM Mutation / Subtitle Interception                    │
│  ┌─────────────────────────┐         ┌──────────────────────────────┐  │
│  │ Content Script          │ ──────► │ Background Service Worker    │  │
│  │ (Captures Raw Captions) │         │ (Dispatches API requests)    │  │
│  └─────────────────────────┘         └──────────────┬───────────────┘  │
└─────────────────────────────────────────────────────┼──────────────────┘
                                                      │ HTTPS / JSON
┌─────────────────────────────────────────────────────┼──────────────────┐
│                      LOCAL / CLOUD BACKEND          ▼                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ FastAPI Microservice                                             │  │
│  │                                                                  │  │
│  │  • POST /api/v1/align                                            │  │
│  │     1. SudachiPy: Tokenize Japanese & extract lemmas/readings    │  │
│  │     2. spaCy: Tokenize & lemmatize English sentence              │  │
│  │     3. JMDict: Retrieve English definitions for Japanese lemmas  │  │
│  │     4. Matcher: Align Japanese tokens <-> English tokens         │  │
│  │     5. Assign synchronized palette colors                        │  │
│  │                                                                  │  │
│  │  • POST /api/v1/vocab (Save vocabulary, sentence context, URL)   │  │
│  │  • GET  /api/v1/vocab (Fetch saved deck for user)                │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │ SQL Queries                      │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │ Supabase (Managed PostgreSQL)                                    │  │
│  │  • Tables: users, vocab_items                                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

## 4. Algorithmic Word-Alignment Pipeline

1. **Input Payload:** Backend receives `{ "ja_text": "...", "en_text": "..." }` (translated beforehand if video source is in another language).
2. **Japanese Parsing:**
   - SudachiPy tokenizes into morphemes: surface form, base lemma, and POS tag.
   - `jaconv` converts Katakana reading to Hiragana; normalizes particle readings (は -> わ, を -> お, へ -> え).
3. **English Parsing:**
   - spaCy tokenizes the sentence and computes root lemmas (e.g., "watched" -> "watch").
4. **Dictionary Lookup & Scoring:**
   - Query local JMDict for English glosses of each Japanese lemma.
   - Calculate lemma-to-gloss intersection score against English tokens in the sentence.
5. **Color & Pairing Synthesis:**
   - Optimal matches are paired: `pair_id = k`.
   - Distinct hex colors from a curated palette are assigned to each `pair_id`.
   - Particles, punctuation, and unmapped words receive a muted default color (`#9CA3AF`).
6. **Return Contract:**
```json
{
  "japanese": [
    { "word": "私", "reading": "わたし", "pair_id": 1, "color": "#3B82F6" },
    { "word": "は", "reading": "わ", "pair_id": null, "color": "#9CA3AF" },
    { "word": "アニメ", "reading": "あにめ", "pair_id": 2, "color": "#EF4444" },
    { "word": "を", "reading": "お", "pair_id": null, "color": "#9CA3AF" },
    { "word": "見ます", "reading": "みます", "pair_id": 3, "color": "#10B981" }
  ],
  "english": [
    { "word": "I", "pair_id": 1, "color": "#3B82F6" },
    { "word": "watch", "pair_id": 3, "color": "#10B981" },
    { "word": "anime", "pair_id": 2, "color": "#EF4444" }
  ]
}
```

## 5. Database Schema (PostgreSQL)

```sql
CREATE TABLE vocab_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    word TEXT NOT NULL,
    reading TEXT NOT NULL,
    english_meaning TEXT NOT NULL,
    part_of_speech TEXT,
    sentence_context_ja TEXT,
    sentence_context_en TEXT,
    video_url TEXT,
    timestamp_seconds INT,
    saved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_vocab_user ON vocab_items(user_id);
```

## 6. Execution Roadmap & Current Status

*   **Phase 1: Project Plumbing & CI/CD** `[COMPLETED]`
    *   Monorepo layout initialized (`extension/`, `backend/`, `.github/workflows/`).
    *   `uv` virtual environment configured with Python.
    *   GitHub Actions CI pipeline configured for automated linting (`flake8`, `black`).
*   **Phase 2: Subtitle Interception & Overlay** `[COMPLETED]`
    *   Manifest V3 setup with active permissions.
    *   `MutationObserver` attached to persistent `.ytp-caption-window-container`.
    *   Dynamic custom subtitle overlay mounted into YouTube player DOM.
*   **Phase 3: Algorithmic Cross-Lingual Alignment Backend** `[IN PROGRESS]`
    *   Install `jamdict`, `spacy` (`en_core_web_sm`), `jaconv`, `sudachipy`.
    *   Build `/api/v1/align` endpoint in FastAPI.
    *   Implement JMDict lookup + bipartite token alignment algorithm.
    *   Assign synchronized color palettes for matching pairs.
*   **Phase 4: Extension Integration & UI Rendering**
    *   Connect `content.js` to send raw text to background service worker.
    *   Background worker calls `/api/v1/align`.
    *   Render dual subtitles with Furigana (`<ruby>`) and matching word colors.
*   **Phase 5: Cloud Persistence & Word Saving**
    *   Create Supabase PostgreSQL instance.
    *   Implement click-to-save listener on Japanese tokens.
    *   Store word, reading, translation context, and video timestamp.
*   **Phase 6: Side Panel Dashboard & Deployment**
    *   Implement `chrome.sidePanel` review interface with seekable timestamps.
    *   Dockerize backend and deploy to Render/Railway.
    *   Complete README with system design diagrams and benchmarking notes.
