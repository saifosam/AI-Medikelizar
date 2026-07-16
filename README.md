# ⚕ AI-Medikelizar — Clinical Reference Tool

**AI-Medikelizar** is a clinical reference tool that lets users ask health-related questions and receive answers grounded strictly in trusted medical sources — PubMed/MEDLINE, CDC, WHO, MedlinePlus, NIH, and PubMed Central. Every claim includes a traceable citation; no answer appears without a source.

---

## The problem

Open-web search engines return an indiscriminate mix of authoritative medical content alongside unverified forums, commercial health sites, and outright misinformation. For clinicians, researchers, and informed patients, separating signal from noise is time-consuming and error-prone.

AI-Medikelizar solves this by **restricting retrieval to a curated allowlist of trusted medical domains**. The AI summarises only what those trusted sources say — and links every claim back to its origin so you can verify, read in context, and draw your own conclusions.

---

## How it works

1. **You ask a clinical question** via a search-bar style input (not a chat interface).
2. **Retrieval engine searches only the trusted allowlist** — PubMed, CDC, WHO, MedlinePlus, NIH, and PubMed Central — using scoped search APIs. No open-web results.
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

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vanilla HTML, CSS, JavaScript (no framework — SPA with hash-based routing) |
| **Design system** | Custom CSS with CSS Grid, Flexbox, custom properties, responsive breakpoints |
| **Typography** | Source Serif 4 (headings), Inter (body), JetBrains Mono (citations / data) |
| **Backend** | Python / FastAPI (in development — RAG pipeline with embeddings + LLM) |
| **Retrieval** | Scoped Custom Search Engine or per-source APIs (configurable) |
| **Dark mode** | CSS custom properties with `prefers-color-scheme` detection, manual toggle, and localStorage persistence |
| **Deployment** | GitHub Pages via GitHub Actions |

---

## Setup & installation

### Prerequisites

- A modern web browser (Chrome, Firefox, Safari, Edge)
- _For the frontend only:_ No build tools required — open `index.html` or deploy to any static host

### Running locally (frontend)

```bash
# Clone the repository
git clone https://github.com/saifosam/AI-Medikelizar.git

# Navigate into the project directory
cd AI-Medikelizar

# Open in your browser
# Option A: Open index.html directly
# Option B: Serve with a local HTTP server (recommended for proper routing)
python -m http.server 8000
# Then visit http://localhost:8000
```

### Backend setup (future)

Once the FastAPI backend is integrated, you will need:

```bash
# Environment variables (create .env at project root)
# Required:
PUBMED_API_KEY=your_ncbi_api_key
OPENAI_API_KEY=your_openai_api_key    # or other LLM provider
CUSTOM_SEARCH_ENGINE_ID=your_cse_id   # optional, for scoped web search

# Optional:
CDC_API_KEY=your_cdc_api_key
WHO_API_KEY=your_who_api_key
```

---

## Project structure

```
AI-Medikelizar/
├── index.html                  # Single-page application entry point
├── css/
│   └── main.css                # Full design system & responsive styles
├── js/
│   └── main.js                 # Application logic, router, demo data
├── .github/
│   └── workflows/
│       └── pages.yml           # GitHub Actions deployment workflow
├── LICENSE                     # MIT license
├── README.md                   # This file
└── .gitignore                  # Git ignore rules
```

### Page views (hash-routed)

| Route | View | Description |
|-------|------|-------------|
| `#home` | **Query** | Search-bar input with example clinical questions |
| `#results` | **Results** | AI-synthesised answer with inline citations + expandable source cards |
| `#trusted-sources` | **Sources** | Allowlist of 6 indexed medical databases/organisations |
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
