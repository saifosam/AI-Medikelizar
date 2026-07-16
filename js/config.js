/* ═══════════════════════════════════════════════════════════
   AI-Medikelizar — Provider & API Configuration
   ═══════════════════════════════════════════════════════════
   Edit this file to set your preferred AI provider and API keys.
   The app reads this config to know which LLM backend to call.
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
     Fill in the settings for your chosen provider.
     Unused providers can be left empty.
  */

  openai: {
    apiKey: "",                    // Your OpenAI API key: sk-...
    model: "gpt-4o-mini",         // Model name: gpt-4o, gpt-4o-mini, gpt-4-turbo, etc.
    endpoint: "https://api.openai.com/v1",  // API base URL (change for proxies)
  },

  ollama: {
    baseUrl: "http://localhost:11434",  // Ollama server URL
    model: "llama3.2",                 // Model: llama3.2, llama3.1, mistral, meditron, etc.
    // No API key needed — Ollama runs locally
  },

  anthropic: {
    apiKey: "",                    // Your Anthropic API key: sk-ant-...
    model: "claude-3-haiku-20240307",  // Model: claude-3-haiku, claude-3.5-sonnet, etc.
    endpoint: "https://api.anthropic.com/v1",
  },

  google: {
    apiKey: "",                    // Your Google AI API key
    model: "gemini-1.5-flash",     // Model: gemini-1.5-flash, gemini-1.5-pro, etc.
    endpoint: "https://generativelanguage.googleapis.com/v1beta",
  },

  custom: {
    apiKey: "",                    // API key for your custom endpoint (if needed)
    endpoint: "",                  // Full URL to your API, e.g. http://localhost:8000/v1
    model: "",                     // Model name your endpoint expects
  },

  /* ── Retrieval settings ── */
  retrieval: {
    maxSources: 8,                 // Max sources to retrieve per query
    minRelevance: 0.7,            // Minimum relevance threshold (0–1)
    cacheResults: true,           // Cache recent results in localStorage
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
      return `${AI_CONFIG.anthropic.endpoint}/messages`;
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
