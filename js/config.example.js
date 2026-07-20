/* ═══════════════════════════════════════════════════════════
   AI-Medikelizar — Frontend Configuration (EXAMPLE)
   ═══════════════════════════════════════════════════════════
   ⚠️  The AI provider and model are controlled by the BACKEND.
      Edit .env (not this file) to change which AI provider
      and model are used. See .env.example for all options.

   This file is only for frontend-specific settings that
   do NOT affect which AI provider the backend uses.
   ═══════════════════════════════════════════════════════════ */

const AI_CONFIG = {
  /* ── Clerk Authentication ── */
  clerk: {
    publishableKey: "",   // Set in index.html or via Vercel env var
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
