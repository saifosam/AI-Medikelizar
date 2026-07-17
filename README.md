# ⚕ AI-Medikelizar — Clinical Reference Tool

**AI-Medikelizar** is a clinical reference tool that lets users ask health-related questions and receive answers grounded strictly in trusted medical sources — PubMed/MEDLINE, CDC, WHO, MedlinePlus, NIH, PubMed Central, and MSD Manuals. Every claim includes a traceable citation; no answer appears without a source.

---

## The problem

Open-web search engines return an indiscriminate mix of authoritative medical content alongside unverified forums, commercial health sites, and outright misinformation. For clinicians, researchers, and informed patients, separating signal from noise is time-consuming and error-prone.

AI-Medikelizar solves this by **restricting retrieval to a curated allowlist of trusted medical domains**. The AI summarises only what those trusted sources say — and links every claim back to its origin so you can verify, read in context, and draw your own conclusions.

---

## How it works

1. **You ask a clinical question** via a search-bar style input (not a chat interface).
2. **Retrieval engine searches only the trusted allowlist** — PubMed, CDC, WHO, MedlinePlus, NIH, PubMed Central, and MSD Manuals — using scoped search APIs. No open-web results.
3. **AI summarises the retrieved evidence** into a clear answer with inline citation markers (<sup>[1]</sup>, <sup>[2]</sup>) pointing to specific source cards.
4. **Source cards display full citation metadata** — title, authors, journal, date, PMID, DOI, and a direct link to the original publication — so you can always read the evidence for yourself.

---

## Trusted sources indexed

| Source | Publisher | Content |
|--------|-----------|---------|
| **PubMed / MEDLINE** | U.S. National Library of Medicine (NIH) | 35M+ citations for biomedical literature, peer-reviewed journals, clinical trials |
| **PubMed Central (PMC)** | U.S. National Library of Medicine (NIH) | Free full-text archive of biomedical and life sciences journal articles |
| **Centers for Disease Control (CDC)** | U.S. Department of Health & Human Services | Public health guidelines, MMWR reports, vaccination recommendations, epidemiological data |
| **World Health Organization (WHO)** | United Nations | Global health guidelines, ICD classification, international health regulations, health policy |
| **MedlinePlus** | U.S. National Library of Medicine (NIH) | Consumer-friendly health information, 1,000+ health topics, drug information, patient handouts |
| **National Institutes of Health (NIH)** | U.S. Department of Health & Human Services | Research summaries, clinical trial registry, disease-specific portals, health disparities data |
| **MSD Manuals** | Merck Sharp & Dohme (MSD) / Merck & Co. | Comprehensive medical reference covering diseases, symptoms, treatments, drug information, and diagnostic guidelines — Professional and Consumer editions |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vanilla HTML, CSS, JavaScript (no framework — SPA with hash-based routing) |
| **Design system** | Custom CSS with CSS Grid, Flexbox, custom properties, responsive breakpoints |
| **Typography** | Source Serif 4 (headings), Inter (body), JetBrains Mono (citations / data) |
| **Backend** | Python / FastAPI (in development — RAG pipeline with embeddings + LLM) |
| **AI provider** | OpenAI API (default) or local models via Ollama (configurable) |
| **Retrieval** | Scoped Custom Search Engine or per-source APIs (configurable) |
| **Dark mode** | CSS custom properties with `prefers-color-scheme` detection, manual toggle, and localStorage persistence |
| **Deployment** | GitHub Pages via GitHub Actions |

---

## Setup & installation

### Prerequisites

- A modern web browser (Chrome, Firefox, Safari, Edge)
- Python 3.10+ (for the backend)
- _For the frontend only:_ No build tools required — open `index.html` or deploy to any static host

### Running locally (frontend only)

```bash
# Clone the repository
git clone https://github.com/saifosam/AI-Medikelizar.git
cd AI-Medikelizar

# Serve with a local HTTP server (recommended for proper routing)
python -m http.server 5500
# Then visit http://localhost:5500
```

The frontend runs in **demo mode** by default — it uses pre-loaded sample data so you can explore the UI without a backend. Real API calls are automatically attempted when the backend is running.

---

### Running the backend (for real queries)

The backend is a Python/FastAPI server that searches PubMed and calls your chosen AI provider.

#### 1. Install Python dependencies

```bash
pip install -r backend/requirements.txt
```

#### 2. Set your API keys securely

There are two ways to configure the backend. **Use `.env` for real keys — it's the secure option and won't be committed to git.**

**Option A (recommended): `.env` file**

Copy the template and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env` with your keys:
```ini
# PubMed (NCBI requires a valid email — even without an API key)
PUBMED_EMAIL=your.email@example.com
PUBMED_API_KEY=your_ncbi_api_key     # Optional: raises rate limit from 3 → 10 req/s

# Choose ONE AI provider group and fill in its keys:
OPENAI_API_KEY=sk-...                # OpenAI
OPENAI_MODEL=gpt-4o-mini
# -or-
OLLAMA_BASE_URL=http://localhost:11434  # Ollama (local, no key needed)
OLLAMA_MODEL=llama3.2
# -or-
ANTHROPIC_API_KEY=sk-ant-...         # Anthropic
# -or-
GOOGLE_API_KEY=...                   # Google Gemini
```

> `.env` is in `.gitignore` — your keys stay safe.

**Option B: `js/config.js` (for frontend-only or quick prototyping)**

Copy the example template to `config.js`:
```bash
cp js/config.example.js js/config.js
```

Edit `js/config.js` to set your preferred provider and keys. **This file is now also in `.gitignore`** — it won't be committed even if you run `git add -A`. See the security section below.

> ⚠️ `js/config.js` is visible in the browser via DevTools. Only use it for local/dev testing. For production, use `.env` and route API calls through the backend.

#### 3. Start the backend server

```bash
# From the project root directory:
uvicorn backend.main:app --reload --port 8000
```

You should see startup logs like:
```
INFO:     AI-Medikelizar Backend starting
INFO:       Provider:  openai
INFO:       PubMed:    API key set (or: no API key, 3 req/s)
INFO:     Application startup complete.
```

#### 4. Test that it works

Open a second terminal and run:

```bash
# Health check — always works, no keys required
curl http://localhost:8000/api/health
# → {"status":"ok","provider":"openai","model":"gpt-4o-mini"}

# Try a query (replace with your own question)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the JNC 8 guidelines for hypertension?"}'
```

If everything is configured, you'll get back a JSON response with `answer` (HTML), `sources` (array of source cards), and `confidence`. If PubMed fails (no email set), you'll get an error response explaining what's missing.

#### 5. Use the frontend with live data

1. Start the backend (step 3 above)
2. Start the frontend on a different port:
   ```bash
   python -m http.server 5500
   ```
3. Open **http://localhost:5500** in your browser
4. Submit a query — the frontend automatically calls `http://localhost:8000/api/query`
5. If the backend isn't running, it gracefully falls back to demo data

---

### AI provider configuration

Edit **`js/config.js`** (or `.env`) to choose your AI provider and set API keys. The config supports five providers:

| Provider | Type | API Key Required |
|----------|------|------------------|
| **OpenAI** | Cloud API | Yes — `sk-...` |
| **Ollama** | Local | No (runs on your machine) |
| **Anthropic** | Cloud API | Yes — `sk-ant-...` |
| **Google Gemini** | Cloud API | Yes |
| **Custom** | OpenAI-compatible endpoint | Optional (e.g., vLLM, TGI, local proxies) |

```bash
# Example: switch to Ollama in js/config.js:
#   provider: "ollama"
#   ollama: { baseUrl: "http://localhost:11434", model: "llama3.2" }
#
# Example: switch to OpenAI in .env:
#   OPENAI_API_KEY=sk-...
#   OPENAI_MODEL=gpt-4o-mini
```

---

### 🔐 Security: keeping your API keys safe

**Short version:** Use `.env` for API keys. `js/config.js` and `.env` are both ignored by git.

| File | Tracked in git? | Contains real keys? | Used by |
|------|----------------|---------------------|---------|
| `js/config.example.js` | ✅ Yes (safe template) | ❌ Placeholders only | Reference template |
| `js/config.js` | ❌ No (`.gitignore`) | ✅ Your real keys | Frontend + Backend |
| `.env.example` | ✅ Yes (safe template) | ❌ Placeholders only | Reference template |
| `.env` | ❌ No (`.gitignore`) | ✅ Your real keys | Backend only (takes priority) |

**How the backend resolves keys (priority order):**

1. `.env` file wins (most secure — never committed)
2. `js/config.js` fallback (also gitignored, but visible in browser DevTools)
3. Hard-coded default

> ⚠️ If you already committed `js/config.js` with real API keys, **rotate those keys immediately** — they're exposed in your git history. Generate new keys from your provider's dashboard, then use `.env` going forward.

---

## Project structure

```
AI-Medikelizar/
├── index.html                  # Single-page application entry point
├── css/
│   └── main.css                # Full design system & responsive styles
├── js/
│   ├── config.example.js       # Safe template — copy to config.js (DO NOT EDIT)
│   ├── config.js               # ⚠️ Your real config — gitignored, never committed
│   └── main.js                 # Application logic, router, demo data
├── backend/
│   ├── __init__.py             # Package marker
│   ├── main.py                 # FastAPI app: /api/query, /api/health, CORS
│   ├── config.py               # Reads config, env vars, PubChem settings
│   ├── models.py               # Pydantic request/response schemas
│   ├── pubmed.py               # PubMed ESearch + EFetch (NCBI E-utilities)
│   ├── ai_providers.py         # 5 providers: OpenAI, Ollama, Anthropic, Google, Custom
│   ├── rag_pipeline.py         # RAG orchestrator: search → retrieve → summarize
│   └── requirements.txt        # fastapi, uvicorn, httpx, python-dotenv
├── .github/
│   └── workflows/
│       └── pages.yml           # GitHub Actions deployment workflow
├── .env.example                # Safe template — copy to .env with your keys
├── .env                        # ⚠️ Your real keys — gitignored, never committed
├── .gitignore                  # Git ignore rules (config.js, .env, etc.)
├── LICENSE                     # MIT license
└── README.md                   # This file
```

### Page views (hash-routed)

| Route | View | Description |
|-------|------|-------------|
| `#home` | **Query** | Search-bar input with example clinical questions |
| `#results` | **Results** | AI-synthesised answer with inline citations + expandable source cards |
| `#trusted-sources` | **Sources** | Allowlist of 7 indexed medical databases/organisations |
| `#about` | **About** | Trust model explanation, technical approach, intended use, full disclaimer |

---

## Design philosophy

AI-Medikelizar deliberately avoids generic "AI chat app" aesthetics:

- **No** purple/blue gradients, rounded chat bubbles, glowing orb avatars, or "AI startup" visual tropes
- **Clinical reference tool** aesthetic — precise, calm, information-dense but uncluttered
- **Typography hierarchy:** Serif headings (medical journal authority) → clean grotesk body → monospace citations
- **Muted palette:** Cool light-gray background, ink-navy/charcoal text, desaturated teal accent for actions/links only
- **Every answer block** visually separates "the answer" from "the sources it came from"
- **Persistent disclaimer** — never a substitute for professional medical advice
- **Minimal, purposeful animation** — answer streaming, source card expansion — nothing decorative

---

## Disclaimer

**AI-Medikelizar is for informational and educational purposes only.** The content generated by this tool does not constitute medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition or treatment.

Never disregard professional medical advice or delay in seeking it because of something you have read on this site. If you think you may have a medical emergency, call your doctor or 911 (or your local emergency number) immediately.

AI-Medikelizar does not recommend or endorse any specific tests, physicians, products, procedures, opinions, or other information that may be referenced in generated responses.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
