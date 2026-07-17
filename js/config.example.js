/* ═══════════════════════════════════════════════════════════
   AI-Medikelizar — Provider & API Configuration (EXAMPLE)
   ═══════════════════════════════════════════════════════════
   ⚠️  DO NOT put real API keys in this file.
      Copy it to config.js and edit THAT file instead.
      config.js is in .gitignore and will NOT be committed.

   Alternatively, set all keys via .env (recommended for
   backend usage) — see .env.example.
   ═══════════════════════════════════════════════════════════ */

const AI_CONFIG = {
  /* ── Active provider ──
     Choose which AI provider to use. Set to one of:
       "openai"     — OpenAI API (GPT-4o, GPT-4o-mini, etc.)
       "ollama"     — Ollama (local, runs on your machine)
       "anthropic"  — Anthropic API (Claude 3.5 Haiku, Sonnet, etc.)
       "google"     — Google AI API (Gemini 1.5 Flash, Pro, etc.)
       "custom"     — Any OpenAI-compatible endpoint (vLLM, TGI, etc.)
  */
  provider: "openai",

  /* ── Provider settings ──
     Fill in your chosen provider below. Leave unused ones empty.
     ⚠️  Use .env for real API keys — more secure!
  */

  openai: {
    apiKey: "",                    // → or set env: OPENAI_API_KEY
    model: "gpt-4o-mini",
    endpoint: "https://api.openai.com/v1",
  },

  ollama: {
    baseUrl: "http://localhost:11434",
    model: "llama3.2",
    // No API key needed — runs locally
  },

  anthropic: {
    apiKey: "",                    // → or set env: ANTHROPIC_API_KEY
    model: "claude-3-haiku-20240307",
  },

  google: {
    apiKey: "",                    // → or set env: GOOGLE_API_KEY
    model: "gemini-1.5-flash",
  },

  custom: {
    apiKey: "",                    // → or set env: CUSTOM_API_KEY
    endpoint: "",                  // → or set env: CUSTOM_ENDPOINT
    model: "",
  },

  /* ── Retrieval settings ── */
  retrieval: {
    maxSources: 8,
    minRelevance: 0.7,
    cacheResults: true,
  },

  /* ── System prompt ── */
  systemPrompt:
    "You are a clinical reference assistant. Answer the user's question using ONLY the provided source texts. " +
    "Cite every factual claim with its source number in square brackets, e.g. [1]. " +
    "Never fabricate references or infer beyond what the sources state. " +
    "If the sources are insufficient to answer, state that clearly. " +
    "Use precise medical terminology but explain it briefly. " +
    "Format your response in clear paragraphs with bold headings for sections.",
};


/* ─── Helper: get active provider config ─── */
function getActiveProvider() {
  const provider = AI_CONFIG.provider;
  return AI_CONFIG[provider] || null;
}

/* ─── Helper: get API endpoint URL for the active provider ─── */
function getApiEndpoint() {
  const p = AI_CONFIG.provider;
  switch (p) {
    case "openai":
      return `${AI_CONFIG.openai.endpoint}/chat/completions`;
    case "ollama":
      return `${AI_CONFIG.ollama.baseUrl}/api/chat`;
    case "anthropic":
      return "https://api.anthropic.com/v1/messages";
    case "google":
      return `${AI_CONFIG.google.endpoint}/models/${AI_CONFIG.google.model}:generateContent`;
    case "custom":
      return AI_CONFIG.custom.endpoint;
    default:
      return null;
  }
}

/* ─── Helper: get headers for the active provider API call ─── */
function getApiHeaders() {
  const p = AI_CONFIG.provider;
  switch (p) {
    case "openai":
      return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${AI_CONFIG.openai.apiKey}`,
      };
    case "ollama":
      return { "Content-Type": "application/json" };
    case "anthropic":
      return {
        "Content-Type": "application/json",
        "x-api-key": AI_CONFIG.anthropic.apiKey,
        "anthropic-version": "2023-06-01",
      };
    case "google":
      return { "Content-Type": "application/json" };
    case "custom":
      return {
        "Content-Type": "application/json",
        ...(AI_CONFIG.custom.apiKey ? { "Authorization": `Bearer ${AI_CONFIG.custom.apiKey}` } : {}),
      };
    default:
      return { "Content-Type": "application/json" };
  }
}

/* ─── Helper: get model name for the active provider ─── */
function getModelName() {
  const p = AI_CONFIG.provider;
  const cfg = AI_CONFIG[p];
  return cfg ? cfg.model : null;
}
