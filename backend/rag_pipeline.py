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
from datetime import datetime

from . import config
from .models import SourceModel, QueryResponse
from .pubmed import search_pubmed
from .ai_providers import get_provider, AIProviderError


async def run_pipeline(query: str) -> QueryResponse:
    """
    Execute the full RAG pipeline:

    Args:
        query: The user's clinical question.

    Returns:
        QueryResponse with answer HTML and source citations.
    """
    # ── Step 1: Retrieve sources from PubMed ──────────
    try:
        raw_sources = await search_pubmed(query)
    except Exception as e:
        # If PubMed fails, return an error message
        return _error_response(
            f"Failed to search PubMed: {str(e)}",
            provider="n/a",
            model="n/a",
        )

    if not raw_sources:
        return _error_response(
            "No relevant sources could be found for your query. "
            "Try rephrasing your question or using broader medical terms.",
            provider="n/a",
            model="n/a",
        )

    # Convert to SourceModel instances
    sources = [SourceModel(**s) for s in raw_sources]

    # ── Step 2: Build the prompt ──────────────────────
    prompt = _build_prompt(query, sources)

    # ── Step 3: Call the AI provider ──────────────────
    try:
        provider = get_provider()
        answer_text = await provider.complete(prompt, config.SYSTEM_PROMPT)
    except AIProviderError as e:
        return _error_response(
            f"AI provider error: {str(e)}",
            provider=config.PROVIDER,
            model=_get_model_name(),
        )
    except Exception as e:
        return _error_response(
            f"Unexpected error calling AI provider: {str(e)}",
            provider=config.PROVIDER,
            model=_get_model_name(),
        )

    # ── Step 4: Convert answer text to HTML ───────────
    answer_html = _text_to_html(answer_text, sources)

    # ── Step 5: Compute confidence ────────────────────
    confidence = _compute_confidence(sources)

    return QueryResponse(
        answer=answer_html,
        sources=sources,
        confidence=confidence,
        provider=provider.name,
        model=provider.model_name,
    )


def _build_prompt(query: str, sources: list[SourceModel]) -> str:
    """Build the prompt with source context for the AI provider."""
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
        "Using ONLY the sources above, answer the clinical question. "
        "Cite each claim with the source number in brackets, e.g. [1]. "
        "If multiple sources support a claim, cite all of them, e.g. [1][2]. "
        "If the evidence is insufficient, state that clearly. "
        "Structure your answer with bold headings for each section."
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


def _compute_confidence(sources: list[SourceModel]) -> str:
    """Determine confidence level based on source relevance scores."""
    if not sources:
        return "limited"
    avg_relevance = sum(s.relevance for s in sources) / len(sources)
    if avg_relevance >= 0.85:
        return "high"
    elif avg_relevance >= 0.7:
        return "moderate"
    else:
        return "limited"


def _get_model_name() -> str:
    """Get the model name from config, or n/a if not set."""
    provider_name = config.PROVIDER
    provider_cfg = getattr(config, f"{provider_name.upper()}_MODEL", None)
    if provider_cfg:
        return provider_cfg
    return "n/a"


def _error_response(message: str, provider: str, model: str) -> QueryResponse:
    """Build an error response as a valid QueryResponse."""
    return QueryResponse(
        answer=f"<p>{message}</p>",
        sources=[],
        confidence="limited",
        provider=provider,
        model=model,
    )
