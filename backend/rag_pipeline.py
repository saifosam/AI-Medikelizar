"""
AI-Medikelizar — RAG Pipeline
===============================
Orchestrates the full retrieval-augmented generation flow:

    1. Search PubMed via E-utilities
    2. Retrieve article metadata
    3. Build a context prompt from the sources
    4. Call the configured AI provider
    5. Parse and return the answer with citations
"""

import re
import logging
from datetime import datetime

from . import config
from .models import SourceModel, QueryResponse
from .pubmed import search_pubmed
from .ai_providers import get_provider, AIProviderError

log = logging.getLogger("ai-medikelizar.rag")


async def run_pipeline(query: str, confidence: str = "medium", context: dict = None, language: str = "en") -> QueryResponse:
    """
    Execute the full RAG pipeline.

    Args:
        query: The user's clinical question.
        confidence: Thoroughness level — "low" (fast), "medium" (balanced), "high" (thorough).
        context: Optional dict with prior conversation context for follow-up queries.
                 Keys: previousQuery, previousAnswer.
        language: Target language code (e.g. "en", "ar") for the AI response.

    Returns:
        QueryResponse with answer HTML and source citations.
    """
    # Resolve confidence preset
    preset = config.CONFIDENCE_PRESETS.get(
        confidence, config.CONFIDENCE_PRESETS["medium"]
    )
    max_sources = preset["max_sources"]
    temperature = preset["temperature"]

    # ── Step 0.5: Rewrite follow-up query with context ──
    search_query = query
    if context and (context.get("previousQuery") or context.get("previousAnswer")):
        try:
            rewritten = await _rewrite_query(query, context)
            if rewritten and rewritten.strip():
                search_query = rewritten.strip()
        except Exception as e:
            log.warning(f"Query rewriting failed (falling back to original): {e}")
    else:
        log.info(f"No context — using original query: '{search_query[:100]}'")

    log.info(f"Search query: '{search_query[:120]}'  sources={max_sources}")

    # ── Step 1: Retrieve sources from PubMed ──────────
    try:
        raw_sources = await search_pubmed(search_query, retmax=max_sources)
    except Exception as e:
        # If PubMed fails, return an error message
        return _error_response(
            f"Failed to search PubMed: {str(e)}",
            provider="n/a",
            model="n/a",
            confidence=confidence,
        )

    if not raw_sources:
        log.warning(f"PubMed returned 0 results for: '{search_query[:120]}'")
        return _error_response(
            "No relevant sources could be found for your query. "
            "Try rephrasing your question or using broader medical terms.",
            provider="n/a",
            model="n/a",
            confidence=confidence,
        )

    log.info(f"PubMed returned {len(raw_sources)} sources")

    # Convert to SourceModel instances
    sources = [SourceModel(**s) for s in raw_sources]

    # ── Step 2: Build the prompt ──────────────────────
    prompt = _build_prompt(query, sources, temperature, language)

    # ── Step 3: Call the AI provider ──────────────────
    try:
        provider = get_provider()
        answer_text = await provider.complete(prompt, config.SYSTEM_PROMPT)
    except AIProviderError as e:
        return _error_response(
            f"AI provider error: {str(e)}",
            provider=config.PROVIDER,
            model=_get_model_name(),
            confidence=confidence,
        )
    except Exception as e:
        return _error_response(
            f"Unexpected error calling AI provider: {str(e)}",
            provider=config.PROVIDER,
            model=_get_model_name(),
            confidence=confidence,
        )

    # ── Step 4: Convert answer text to HTML ───────────
    answer_html = _text_to_html(answer_text, sources)

    return QueryResponse(
        answer=answer_html,
        sources=sources,
        confidence=confidence,
        provider=provider.name,
        model=provider.model_name,
    )


async def _rewrite_query(query: str, context: dict) -> str:
    """
    Use the AI provider to rewrite a follow-up query by resolving pronouns
    and implicit references using prior conversation context.

    Args:
        query: The raw follow-up question (e.g. "what ages does it happen to").
        context: Dict with previousQuery and/or previousAnswer.

    Returns:
        A self-contained search query (e.g. "diabetes insipidus age of onset").
        If the follow-up appears to be a new unrelated topic, returns the
        original query unchanged.
    """
    prev_query = (context.get("previousQuery") or "").strip()
    prev_answer = (context.get("previousAnswer") or "").strip()

    # Shorten the previous answer to just the first ~600 chars for context
    if len(prev_answer) > 600:
        prev_answer = prev_answer[:600] + "..."

    rewrite_prompt = (
        f"You are a medical query rewriter. Your job is to rewrite follow-up questions "
        f"into self-contained PubMed search queries by resolving pronouns and implicit references.\n\n"
        f"## Previous Query\n{prev_query}\n\n"
        f"## Previous Answer (summary)\n{prev_answer}\n\n"
        f"## Follow-up Question\n{query}\n\n"
        f"## Instructions\n"
        f"1. If the follow-up is a NEW unrelated topic, output the EXACT original query unchanged.\n"
        f"2. If the follow-up clearly REFERENCES the previous topic, rewrite it into a concise, "
        f"self-contained PubMed search query. Replace pronouns ('it', 'that', 'this condition', etc.) "
        f"with the actual medical terms from the previous context.\n"
        f"3. Output ONLY the rewritten query — no explanations, no quotation marks, no prefixes.\n"
        f"4. Keep the output brief (under 15 words), suitable for PubMed search.\n"
        f"5. Use standard medical terminology where possible.\n"
    )

    try:
        provider = get_provider()
        rewritten = await provider.complete(
            rewrite_prompt,
            "You are a precise query rewriter. Output only the rewritten query."
        )
        raw_response = rewritten
        rewritten = rewritten.strip().strip('"').strip("'")

        if not rewritten:
            log.warning("Rewrite returned empty response, falling back to original")
            return query

        if len(rewritten) > 200:
            log.warning(f"Rewrite too long ({len(rewritten)} chars), falling back. First 150 chars: {raw_response[:150]}")
            return query

        log.info(f"Rewrite OK: '{query[:60]}' => '{rewritten[:100]}'")
        return rewritten

    except Exception as e:
        log.warning(f"Rewrite failed ({e}), falling back to original query")
        return query


def _build_prompt(query: str, sources: list[SourceModel], temperature: float = 0.3, language: str = "en") -> str:
    """Build the prompt with source context for the AI provider."""
    # Map language codes to full names for the AI
    LANG_MAP = {
        "en": "English",
        "ar": "Arabic",
    }
    target_lang = LANG_MAP.get(language, "English")

    confidence_note = (
        "Be concise and direct. Prioritise the most clinically relevant findings. "
        if temperature >= 0.5 else
        "Be thorough and detailed. Cover all relevant aspects comprehensively. "
        if temperature <= 0.15 else
        "Provide a balanced answer with appropriate detail. "
    )

    parts = [
        f"## Clinical Question\n{query}\n",
        f"## Retrieved Evidence ({len(sources)} sources)\n",
    ]

    for i, src in enumerate(sources, start=1):
        parts.append(f"Source [{i}]:")
        parts.append(f"  Title: {src.title}")
        parts.append(f"  Authors: {src.authors}")
        parts.append(f"  Journal: {src.journal}, {src.date}")
        if src.doi:
            parts.append(f"  DOI: {src.doi}")
        parts.append(f"  Abstract: {src.abstract}")
        parts.append("")  # blank line

    parts.append(
        "## Instructions\n"
        f"{confidence_note}"
        "Using ONLY the sources above, answer the clinical question. "
        "Cite each claim with the source number in brackets, e.g. [1]. "
        "If multiple sources support a claim, cite all of them, e.g. [1][2]. "
        "If the evidence is insufficient, state that clearly. "
        "Structure your answer with bold headings for each section.\n"
        f"\nIMPORTANT: You MUST write your entire answer in {target_lang}. "
        "Translate all medical terminology accurately. "
        f"If the user wrote their query in a different language, still respond in {target_lang}.\n"
    )

    return "\n".join(parts)


def _text_to_html(text: str, sources: list[SourceModel]) -> str:
    """Convert plain text answer to HTML with inline citation markers.

    Finds patterns like [1], [1][2], [1,2] and converts them to clickable
    <sup> citation markers.
    """
    # Escape HTML in the text first
    text = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )

    # Convert markdown bold (**text**) to HTML bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Convert markdown headings to bold paragraphs
    text = re.sub(r'^###\s+(.+)$', r'<strong>\1</strong>', text, flags=re.MULTILINE)

    # Convert citation markers like [1], [1][2], [1,2,3] to sup tags
    def _replace_citation(match):
        content = match.group(1)
        # Split on common delimiters
        ids = re.findall(r'\d+', content)
        if not ids:
            return match.group(0)
        # Build a single sup with space separation
        markers = "".join(
            f'<sup class="citation-marker" data-source-id="{i}" '
            f'tabindex="0" role="button" aria-label="Source {i}">[{i}]</sup>'
            for i in ids
        )
        return markers

    text = re.sub(r'\[([\d,\s]+)\]', _replace_citation, text)

    # Convert newlines to <p> paragraphs
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    html_paragraphs = []
    for para in paragraphs:
        # If it's already wrapped in a tag, don't double-wrap
        if para.startswith("<"):
            html_paragraphs.append(f"<p>{para}</p>")
        else:
            html_paragraphs.append(f"<p>{para}</p>")

    return "\n".join(html_paragraphs)


def _get_model_name() -> str:
    """Get the model name from config, or n/a if not set."""
    provider_name = config.PROVIDER
    provider_cfg = getattr(config, f"{provider_name.upper()}_MODEL", None)
    if provider_cfg:
        return provider_cfg
    return "n/a"


def _error_response(message: str, provider: str, model: str, confidence: str = "medium") -> QueryResponse:
    """Build an error response as a valid QueryResponse."""
    return QueryResponse(
        answer=f"<p>{message}</p>",
        sources=[],
        confidence=confidence,
        provider=provider,
        model=model,
    )
