# ⚕ AI-Medikelizar — Clinical Reference Tool

**AI-Medikelizar** is a clinical reference tool that lets users ask health-related questions and receive answers grounded strictly in trusted medical sources — PubMed/MEDLINE, CDC, WHO, MedlinePlus, NIH, PubMed Central, and MSD Manuals. Every claim includes a traceable citation; no answer appears without a source.

Built with a vanilla JavaScript SPA frontend, a Python/FastAPI RAG pipeline backend, Clerk authentication, and Paymob payment integration for the Egyptian market.

---

## Features

- **Evidence-based answers** — Retrieval restricted to a curated allowlist of trusted medical domains
- **Citation-anchored generation** — Every factual claim linked to a source card with title, authors, journal, PMID, DOI, and direct link
- **Confidence levels** — Fast (~3 sources), Balanced (~6 sources), Thorough (~12 sources)
- **Follow-up queries** — Ask clarifying questions with conversation context preserved
- **Clerk authentication** — Sign-in/sign-up with email, Google, GitHub, and more
- **Role-based admin dashboard** — Shield icon visible only to whitelisted admin emails; 3-layer security
- **Subscription tiers** — Free (5 queries/day), Premium (50/day), VIP (unlimited)
- **Paymob payments** — Egyptian payment gateway (card + mobile wallets)
- **Dark/light mode** — System-aware with manual toggle and localStorage persistence
- **Rate limiting** — 30 queries/minute per IP (configurable)
- **Page view tracking** — Basic analytics for usage monitoring
- **Responsive design** — Works on desktop, tablet, and mobile
- **Deployed on Vercel** — Static frontend + serverless Python backend on the same domain

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
| **Backend** | Python / FastAPI — RAG pipeline with embeddings + LLM |
| **AI providers** | Ollama (local), Google Gemini, Groq (free tier), OpenRouter, OpenAI, Anthropic, Custom (configurable) |
| **Retrieval** | PubMed E-utilities (ESearch + EFetch) |
| **Authentication** | Clerk (pre-built UI components, session management, webhooks) |
| **Payments** | Paymob (Egyptian payment gateway — card payments + mobile wallets) |
| **Database** | SQLite via SQLAlchemy (user sync, subscription records, query logs, page views) |
| **Rate limiting** | slowapi (configurable per-endpoint) |
| **Dark mode** | CSS custom properties with `prefers-color-scheme` detection, manual toggle, and localStorage persistence |
| **Deployment** | Vercel (frontend static + serverless Python backend via ASGI) |

---

## Project structure

```
AI-Medikelizar/
├── index.html                  # Single-page application entry point
├── css/
│   └── main.css                # Full design system & responsive styles (1000+ lines)
├── js/
│   ├── config.example.js       # Safe template — copy to config.js (DO NOT EDIT)
│   ├── config.js               # ⚠️ Your real config — gitignored, never committed
│   └── main.js                 # App logic, router, admin, pricing, theme, auth
├── backend/
│   ├── __init__.py             # Package marker
│   ├── main.py                 # FastAPI app: all endpoints, CORS, lifespan, middleware
│   ├── config.py               # Reads env vars with fail-fast validation
│   ├── app.py                  # Non-sensitive defaults (confidence presets, prompts)
│   ├── models.py               # Pydantic schemas + SQLAlchemy models
│   ├── database.py             # SQLAlchemy engine, session, init_db
│   ├── auth.py                 # Clerk webhook handler, session verification, middleware
│   ├── admin.py                # Admin dashboard API (Clerk API fallback for Vercel)
│   ├── subscriptions.py        # Paymob payment integration, tier management
│   ├── pubmed.py               # PubMed ESearch + EFetch (NCBI E-utilities)
│   ├── ai_providers.py         # 7 providers: Ollama, Google, Groq, OpenRouter, OpenAI, Anthropic, Custom
│   ├── rag_pipeline.py         # RAG orchestrator: search → retrieve → summarize
│   ├── requirements.txt        # Python dependencies
│   └── ai_medikelizar.db       # SQLite database (gitignored; auto-created on first run)
├── api/
│   └── index.py                # Vercel serverless entry point (ASGI app wrapper)
├── .github/
│   └── workflows/
│       └── pages.yml           # GitHub Pages deployment workflow (alternative)
├── vercel.json                 # Vercel deployment config (rewrites, headers, function settings)
├── .env.example                # Safe template — copy to .env with your keys
├── .env                        # ⚠️ Your real keys — gitignored, never committed
├── .gitignore                  # Git ignore rules (config.js, .env, .vercel, *.db, *.log)
├── LICENSE                     # MIT license
├── README.md                   # This file
└── run.py                      # Local dev launcher (uvicorn + auto-open browser)
```

### Page views (hash-routed SPA)

| Route | View | Description |
|-------|------|-------------|
| `#home` | **Query** | Search-bar input with example clinical questions |
| `#results` | **Results** | AI-synthesised answer with inline citations + expandable source cards |
| `#pricing` | **Pricing** | Subscription tier comparison with monthly/annual toggle |
| `#trusted-sources` | **Sources** | Allowlist of 7 indexed medical databases/organisations |
| `#about` | **About** | Trust model explanation, technical approach, intended use, full disclaimer |
| `#admin` | **Admin** | Dashboard with user stats, recent users table, subscription breakdown (admins only) |

---

## Setup & installation

### Prerequisites

- A modern web browser (Chrome, Firefox, Safari, Edge)
- Python 3.10+ (for the backend)
- _For the frontend only:_ No build tools required — open `index.html` or deploy to any static host

### Running locally (frontend only — demo mode)

The frontend runs in **demo mode** by default — it uses pre-loaded sample data so you can explore the UI without a backend.

```bash
# Clone the repository
git clone https://github.com/saifosam/AI-Medikelizar.git
cd AI-Medikelizar

# Serve with a local HTTP server (recommended for proper routing)
python -m http.server 5500
# Then visit http://localhost:5500
```

Real API calls are automatically attempted when the backend is running. If the backend isn't reachable, it gracefully falls back to demo data.

---

### Running the full stack (backend + frontend)

#### 1. Install Python dependencies

```bash
pip install -r backend/requirements.txt
```

#### 2. Configure environment variables

Create a `.env` file in the project root (or `backend/.env`). Copy the template to start:

```bash
cp .env.example .env
```

At minimum, for the backend to start without crashing, you need:

```ini
# PubMed (NCBI requires a valid email — even without an API key)
PUBMED_EMAIL=your.email@example.com
PUBMED_API_KEY=your_ncbi_api_key     # Optional: raises rate limit from 3 → 10 req/s

# Choose ONE AI provider (see below for all options)
AI_PROVIDER=ollama                   # or: google, groq, openrouter, openai, anthropic, custom
```

For a full list of all configurable env vars, see [Environment Variables Reference](#environment-variables-reference).

> ⚠️ `.env` is in `.gitignore` — your keys stay safe.

#### 3. Start the backend server

```bash
# From the project root directory — serves both backend API and frontend static files
uvicorn backend.main:app --reload --port 8000
```

Or use the convenience launcher:

```bash
python run.py
```

This starts the server and automatically opens `http://localhost:8000` in your browser.

You should see startup logs like:

```
  ╔══════════════════════════════════════════════════════════════════════╗
  ║                 AI-Medikelizar — Environment Check                 ║
  ╚══════════════════════════════════════════════════════════════════════╝

  Variable                        Status       Purpose
  ────────────────────────────── ──────────── ────────────────────────────────────

  INFO:     AI-Medikelizar Backend starting
  INFO:       Provider:      ollama
  INFO:       Model:         qwen2.5-coder:7b
  INFO:       API key:       NOT SET — will fail if not a local provider
  INFO:       Confidence:    medium (default)
  INFO:       PubMed:        no API key (3 req/s)
  INFO:       Rate limit:    enabled
  INFO:       Admin emails:  admin@ai-medikelizar.com, saifosam.business@gmail.com, ...
  INFO:       Payments:      not configured
```

#### 4. Test that it works

```bash
# Health check — always works, no keys required
curl http://localhost:8000/api/health
# → {"status":"ok","provider":"ollama","model":"qwen2.5-coder:7b",...}

# Try a query (replace with your own question)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the JNC 8 guidelines for hypertension?"}'
```

If everything is configured, you'll get back a JSON response with `answer` (HTML), `sources` (array of source cards), and `confidence`.

---

## AI provider configuration

The backend supports **7 AI providers**. Set `AI_PROVIDER` in `.env` to choose one:

| Provider | `AI_PROVIDER` value | API Key Required | Notes |
|----------|---------------------|------------------|-------|
| **Ollama** (local) | `ollama` | No | Runs locally on your machine. Default model: `qwen2.5-coder:7b` |
| **Google Gemini** | `google` | Yes — `GOOGLE_API_KEY` | Free tier available. Default model: `gemini-2.0-flash-lite` |
| **Groq** | `groq` | Yes — `GROQ_API_KEY` | Free tier (no credit card needed). Default model: `llama-3.1-8b-instant` |
| **OpenRouter** | `openrouter` | Yes — `OPENROUTER_API_KEY` | Access many models through one API. Default model: `gpt-4o-mini` |
| **OpenAI** | `openai` | Yes — `OPENAI_API_KEY` | Default model: `gpt-4o-mini` |
| **Anthropic** | `anthropic` | Yes — `ANTHROPIC_API_KEY` | Default model: `claude-3-haiku-20240307` |
| **Custom** | `custom` | Optional | OpenAI-compatible endpoint (e.g., vLLM, TGI, local proxies) |

### Example configurations

**Using Ollama (local, free):**
```ini
AI_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_BASE_URL=http://localhost:11434    # Default Ollama port
```

**Using Google Gemini (free tier available):**
```ini
AI_PROVIDER=google
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_MODEL=gemini-2.0-flash-lite
```

**Using Groq (free, no credit card):**
```ini
AI_PROVIDER=groq
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
```

---

## Clerk authentication setup

AI-Medikelizar uses [Clerk](https://clerk.com) for authentication. Clerk provides pre-built sign-in/sign-up UI components and session management.

### Step 1: Create a Clerk application

1. Go to **[dashboard.clerk.com](https://dashboard.clerk.com)** and sign up or log in
2. Click **Add Application**
3. Name it (e.g., "AI-Medikelizar")
4. Choose sign-in methods: Email (required), plus Google, GitHub, etc. as desired
5. Click **Create**

### Step 2: Get your API keys

In the Clerk Dashboard → **API Keys**:

| Key | Where to use it |
|-----|-----------------|
| **Publishable Key** (`pk_test_...`) | Goes in `index.html` (already pre-configured for development) |
| **Secret Key** (`sk_test_...`) | Goes in `.env` as `CLERK_SECRET_KEY` |

### Step 3: Configure Clerk for local development

**In `index.html`**, update the `data-clerk-publishable-key` attribute on the Clerk JS script tag:

```html
<script
  defer
  crossorigin="anonymous"
  data-clerk-publishable-key="pk_test_YOUR_PUBLISHABLE_KEY"
  src="https://YOUR_CLERK_DOMAIN.clerk.accounts.dev/npm/@clerk/clerk-js@6/dist/clerk.browser.js"
  type="text/javascript"
></script>
```

Also update the Clerk UI bundle URL to your Clerk domain.

**In `.env`**, add your secret key:

```ini
CLERK_SECRET_KEY=sk_test_YOUR_SECRET_KEY
```

### Step 4: Set up the Clerk webhook (user sync)

The webhook syncs users from Clerk to the local database when they sign up, update their profile, or delete their account.

1. In Clerk Dashboard → **Webhooks**
2. Click **Add Endpoint**
3. **Endpoint URL:** `https://your-domain.com/api/auth/webhook` (or `http://localhost:8000/api/auth/webhook` for local dev)
4. **Events to subscribe to:** Select `user.created`, `user.updated`, `user.deleted`
5. Click **Create**
6. Copy the **Signing Secret** (starts with `whsec_...`)

**In `.env`:**
```ini
CLERK_WEBHOOK_SECRET=whsec_YOUR_SIGNING_SECRET
```

> **Note:** The webhook is optional. If not configured, users are created on-the-fly from their Clerk session data when they first make an API request.

---

## Admin dashboard configuration

The admin dashboard is protected by a **3-layer security model**:

| Layer | Where | What it does |
|-------|-------|--------------|
| **Layer 1** | `auth.py` middleware | Protects all `/api/admin/*` routes. Returns 401 if no valid session token |
| **Layer 2** | `admin.py` dependency | `require_admin()` checks the user's email against the whitelist. Returns 403 if not admin |
| **Layer 3** | `main.js` (client) | Hides the shield icon entirely for non-admin users. Admin buttons never render |

### Configuring admin emails

In `.env`, set the `ADMIN_EMAILS` variable:

```ini
ADMIN_EMAILS=saifosam.business@gmail.com,yassinadeleid95@gmail.com,youssef.shabayek56@gmail.com,yjhf04508@gmail.com
```

Default (if not set):

```
admin@ai-medikelizar.com,saifosam.business@gmail.com,yassinadeleid95@gmail.com,youssef.shabayek56@gmail.com,yjhf04508@gmail.com
```

### Accessing the admin dashboard

1. Sign in with an admin email address
2. Click the shield icon in the top-right header
3. Or navigate directly to `/#admin`

The dashboard shows:
- **Stats cards:** Total users, new users (7d), total queries, queries (7d), total revenue, active subscriptions, users by tier
- **Recent users table:** Email, name, tier, subscription status, admin badge, join date
- **Subscription breakdown:** Basic / Premium / VIP counts and estimated MRR

On Vercel (where SQLite is read-only), the dashboard falls back to fetching user data directly from **Clerk's API** using `CLERK_SECRET_KEY`.

---

## Paymob payment setup (subscriptions)

AI-Medikelizar uses [Paymob](https://paymob.com) as the payment gateway for the Egyptian market.

### Step 1: Create a Paymob account

1. Go to **[accept.paymob.com](https://accept.paymob.com)** and sign up
2. Complete the onboarding (business details, bank account)
3. Go to **Developers** → **API Keys** to get your keys

### Step 2: Create payment integrations

1. In Paymob Dashboard → **Payment Integrations**
2. Create a **Card** integration (for card payments)
3. Create a **Mobile Wallet** integration (for Vodafone Cash, etc.)
4. Note the **Integration IDs** for each

### Step 3: Configure environment variables

```ini
PAYMOB_API_KEY=your_paymob_api_key
PAYMOB_PUBLIC_KEY=your_paymob_public_key
PAYMOB_WEBHOOK_SECRET=your_paymob_webhook_hmac_secret
PAYMOB_INTEGRATION_ID_CARDS=123456        # Card payment integration ID
PAYMOB_INTEGRATION_ID_WALLETS=654321      # Mobile wallet integration ID
PAYMOB_PREMIUM_PRICE_CENTS=2999           # Premium tier price in EGP piastres (29.99 EGP)
PAYMOB_VIP_PRICE_CENTS=8999               # VIP tier price in EGP piastres (89.99 EGP)
```

### Step 4: Set up the Paymob webhook

1. In Paymob Dashboard → **Webhooks**
2. Set the **Webhook URL** to: `https://your-domain.com/api/subscriptions/webhook`
3. In `.env`, set `PAYMOB_WEBHOOK_SECRET` to the HMAC secret from Paymob

### Subscription tiers

| Tier | Price | Queries/day | Features |
|------|-------|-------------|----------|
| **Basic** | Free | 5 | Standard speed, basic citations, email support |
| **Premium** | 29.99 EGP/mo | 50 | Faster priority, detailed citations, priority email |
| **VIP** | 89.99 EGP/mo | Unlimited | Fastest priority, full citations with abstracts, priority support + chat, early access |

---

## Deploy to Vercel

AI-Medikelizar is designed to deploy easily on Vercel — the frontend as a static site and the backend as a serverless Python function.

### Prerequisites

- A [Vercel](https://vercel.com) account (free Hobby tier works)
- Your project pushed to a [GitHub](https://github.com) repository
- API keys configured as Vercel Environment Variables

### One-click deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fsaifosam%2FAI-Medikelizar)

### Manual deploy

#### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/AI-Medikelizar.git
git push -u origin main
```

#### 2. Import to Vercel

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repository
3. Vercel auto-detects the project settings from `vercel.json`
4. Framework preset: **Other**
5. Root directory: `./` (project root)
6. Build command: _None_ (leave blank)
7. Output directory: _None_ (leave blank)

#### 3. Set environment variables

In Vercel project dashboard → **Settings** → **Environment Variables**, add the following for the **Production** environment:

**Required for basic operation:**
```
PUBMED_EMAIL=your.email@example.com
PUBMED_API_KEY=your_ncbi_api_key    # Optional but recommended
```

**AI Provider (choose at least one):**
```
AI_PROVIDER=groq                     # Groq is great for free tier on Vercel
GROQ_API_KEY=gsk_your_groq_key       # Free, no credit card needed
```

**Authentication (optional — app runs without, but no sign-in):**
```
CLERK_SECRET_KEY=sk_test_your_clerk_secret_key
CLERK_WEBHOOK_SECRET=whsec_your_webhook_secret
```

**Payments (optional — subscription features):**
```
PAYMOB_API_KEY=your_paymob_api_key
PAYMOB_PUBLIC_KEY=your_paymob_public_key
PAYMOB_WEBHOOK_SECRET=your_webhook_secret
PAYMOB_INTEGRATION_ID_CARDS=123456
PAYMOB_INTEGRATION_ID_WALLETS=654321
PAYMOB_PREMIUM_PRICE_CENTS=2999
PAYMOB_VIP_PRICE_CENTS=8999
```

**Admin emails (defaults are used if not set):**
```
ADMIN_EMAILS=saifosam.business@gmail.com,yassinadeleid95@gmail.com,youssef.shabayek56@gmail.com,yjhf04508@gmail.com
```

> ⚠️ Set the Clerk webhook endpoint URL in your Clerk Dashboard to `https://your-project.vercel.app/api/auth/webhook`

#### 4. Deploy

Vercel automatically deploys on every `git push` to the main branch. You can also trigger a manual redeploy:

```bash
vercel deploy --prod
```

- **Frontend:** `https://your-project.vercel.app`
- **Backend API:** `https://your-project.vercel.app/api/health`
- **Admin dashboard:** `https://your-project.vercel.app/#admin` (after signing in with admin email)

### Vercel architecture

```
                          ┌──────────────────────┐
                          │   Vercel Edge Network │
                          └──────────┬───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                 │
                    ▼                ▼                 ▼
           ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
           │ Static Files  │  │   /api/*     │  │   SPA        │
           │ (HTML/CSS/JS) │  │  Serverless  │  │   Catch-all  │
           │              │  │   Function   │  │   → index.html│
           └──────────────┘  └──────┬───────┘  └──────────────┘
                                    │
                           ┌────────┴────────┐
                           │  FastAPI Backend │
                           │  Python 3.12    │
                           │  RAG Pipeline   │
                           └─────────────────┘
```

### ⚠️ Vercel limitations (Hobby plan)

| Limitation | Impact |
|------------|--------|
| **Serverless timeout: 10s** | "Thorough" confidence level may time out. Upgrade to Pro ($20/mo) for 30s timeout |
| **SQLite is read-only** | The database file can't be created on Vercel's filesystem. The app falls back to Clerk API for admin data and uses in-memory user objects |
| **512MB memory** | Sufficient for PubMed queries + AI response. Upgrade to Pro for more |

---

## 🔐 Security architecture

### 3-layer auth model

```
                          ┌─────────────────────────────┐
                          │     Browser (Client)         │
                          │  Layer 3: Shield icon hidden │
                          │  for non-admin users         │
                          └──────────┬──────────────────┘
                                     │ Session token / cookie
                                     ▼
                          ┌─────────────────────────────┐
                          │  FastAPI Middleware          │
                          │  Layer 1: Token presence     │
                          │  check on /api/admin/*       │
                          │  Returns 401 if no token     │
                          └──────────┬──────────────────┘
                                     ▼
                          ┌─────────────────────────────┐
                          │  Route Handler Dependency   │
                          │  Layer 2: require_admin()    │
                          │  Email whitelist check       │
                          │  Returns 403 if not admin    │
                          └─────────────────────────────┘
```

### API key protection

| File | Tracked in git? | Contains real keys? | Notes |
|------|----------------|---------------------|-------|
| `js/config.example.js` | ✅ Yes | ❌ Placeholders only | Safe template reference |
| `js/config.js` | ❌ No (`.gitignore`) | ✅ Your real config | Visible in browser DevTools — dev only |
| `.env.example` | ✅ Yes | ❌ Placeholders only | Safe template reference |
| `.env` | ❌ No (`.gitignore`) | ✅ Your real keys | Server-side only — never exposed |

### Database security

- `backend/ai_medikelizar.db` is in `.gitignore` — never committed
- On Vercel, SQLite is read-only; all operations gracefully fall back to Clerk API
- User passwords are never stored — authentication is handled entirely by Clerk

---

## API reference

### Public endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/health` | Health check with provider info | None |
| `POST` | `/api/query` | Submit a clinical question | Rate-limited (30/min) |
| `POST` | `/api/auth/webhook` | Clerk webhook (sync users) | Webhook signature |
| `GET` | `/api/auth/me` | Current user info (email, name, admin status) | Session token |
| `GET` | `/api/subscriptions/pricing` | Subscription tier definitions | None |
| `GET` | `/api/subscriptions/status` | User's subscription status | Session token |
| `POST` | `/api/subscriptions/create-checkout` | Create Paymob checkout | Session token |
| `POST` | `/api/subscriptions/create-portal-session` | Subscription management | Session token |
| `POST` | `/api/subscriptions/webhook` | Paymob payment webhook | HMAC signature |

### Protected endpoints (admin only)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/dashboard` | Aggregated stats (users, queries, revenue) |
| `GET` | `/api/admin/users` | List all users with subscription info |

### Query endpoint

**`POST /api/query`**

```json
{
  "query": "What are the standard treatments for adult-onset asthma?",
  "confidence": "medium",
  "context": {
    "previousQuery": "...",
    "previousAnswer": "..."
  }
}
```

**Response:**

```json
{
  "answer": "<p>Based on the retrieved evidence...</p>",
  "sources": [
    {
      "id": 1,
      "title": "Source title",
      "authors": "Author et al.",
      "journal": "Journal Name",
      "date": "2024-01-15",
      "doi": "10.1000/example",
      "pmid": "12345678",
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
      "abstract": "Study abstract...",
      "publisher": "Publisher",
      "relevance": 0.94
    }
  ],
  "confidence": "high",
  "provider": "groq",
  "model": "llama-3.1-8b-instant"
}
```

---

## Environment variables reference

### Required for basic operation

| Variable | Description | Default |
|----------|-------------|---------|
| `PUBMED_EMAIL` | Your email for PubMed E-utilities | `user@example.com` |

### AI Provider (choose one group)

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | Active provider: `ollama`, `google`, `groq`, `openrouter`, `openai`, `anthropic`, `custom` | `ollama` |

**Ollama (local):**
| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | Ollama model name | `qwen2.5-coder:7b` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |

**Google Gemini:**
| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google Gemini API key | — |
| `GOOGLE_MODEL` | Gemini model name | `gemini-2.0-flash-lite` |

**Groq (free, no credit card):**
| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | — |
| `GROQ_MODEL` | Groq model name | `llama-3.1-8b-instant` |

**OpenRouter:**
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | — |
| `OPENROUTER_MODEL` | Model name | `gpt-4o-mini` |

**Legacy providers (OpenAI, Anthropic, Custom):**
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `CUSTOM_API_KEY` | Custom endpoint API key | — |
| `CUSTOM_ENDPOINT` | Custom base URL | — |

### Authentication (Clerk)

| Variable | Description | Default |
|----------|-------------|---------|
| `CLERK_SECRET_KEY` | Clerk API secret key (`sk_test_...` or `sk_live_...`) | — |
| `CLERK_WEBHOOK_SECRET` | Clerk webhook signing secret (`whsec_...`) | — |

### Admin

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_EMAILS` | Comma-separated admin email addresses | Built-in defaults (see above) |

### Payments (Paymob)

| Variable | Description | Default |
|----------|-------------|---------|
| `PAYMOB_API_KEY` | Paymob secret API key | — |
| `PAYMOB_PUBLIC_KEY` | Paymob public key for checkout | — |
| `PAYMOB_WEBHOOK_SECRET` | Paymob webhook HMAC secret | — |
| `PAYMOB_INTEGRATION_ID_CARDS` | Integration ID for card payments | — |
| `PAYMOB_INTEGRATION_ID_WALLETS` | Integration ID for mobile wallets | — |
| `PAYMOB_PREMIUM_PRICE_CENTS` | Premium tier price in EGP piastres | `2999` (29.99 EGP) |
| `PAYMOB_VIP_PRICE_CENTS` | VIP tier price in EGP piastres | `8999` (89.99 EGP) |

### Retrieval

| Variable | Description | Default |
|----------|-------------|---------|
| `PUBMED_API_KEY` | NCBI API key (increases rate limit from 3 → 10 req/s) | — |
| `DEFAULT_CONFIDENCE` | Default confidence level: `low`, `medium`, `high` | `medium` |
| `MAX_SOURCES` | Maximum number of sources to return | `8` |
| `MIN_RELEVANCE` | Minimum relevance score (0.0–1.0) | `0.7` |
| `CACHE_RESULTS` | Cache query results (`true`/`false`) | `true` |

### Rate limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `RATE_LIMIT_ENABLED` | Enable rate limiting | `true` |

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
