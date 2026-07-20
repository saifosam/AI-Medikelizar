"""
Tests for the RAG pipeline query rewriting logic.

Tests _rewrite_query() by mocking the AI provider so no API keys are needed.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock


class TestRewriteQuery(unittest.TestCase):
    """Test the _rewrite_query function with a mocked AI provider."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _run_async(self, coro):
        """Run an async function synchronously in the test."""
        return self.loop.run_until_complete(coro)

    # ── Helpers to build mocked provider ──────────────────────────────

    def _mock_provider(self, return_text: str):
        """Create a mock provider that returns the given text."""
        provider = MagicMock()
        provider.name = "mock"
        provider.model_name = "mock-model"
        provider.complete = AsyncMock(return_value=return_text)
        return provider

    def _mock_provider_failure(self, error: Exception = None):
        """Create a mock provider that raises an exception."""
        provider = MagicMock()
        provider.complete = AsyncMock(
            side_effect=error or Exception("Provider unavailable")
        )
        return provider

    # ── Tests ─────────────────────────────────────────────────────────

    @patch("backend.rag_pipeline.get_provider")
    def test_resolves_pronoun_with_medical_term(self, mock_get_provider):
        """
        Follow-up 'what ages does it happen to' after 'diabetes symptoms'
        should resolve 'it' → 'diabetes insipidus' → produce a self-contained
        search query like 'diabetes insipidus age of onset'.
        """
        mock_get_provider.return_value = self._mock_provider(
            "diabetes insipidus age of onset"
        )

        from backend.rag_pipeline import _rewrite_query

        result = self._run_async(_rewrite_query(
            query="what ages does it happen to",
            context={
                "previousQuery": "diabetes symptoms",
                "previousAnswer": (
                    "Based on the retrieved evidence, diabetes insipidus (DI) is a "
                    "condition characterized by excessive thirst and excretion of large "
                    "amounts of dilute urine. Central DI results from ADH deficiency, "
                    "while nephrogenic DI results from renal resistance to ADH."
                ),
            },
        ))

        self.assertEqual(result, "diabetes insipidus age of onset")

        # Verify the provider was called with the right kind of prompt
        call_args, call_kwargs = mock_get_provider.return_value.complete.call_args
        prompt, system_prompt = call_args
        self.assertIn("what ages does it happen to", prompt)
        self.assertIn("diabetes symptoms", prompt)
        self.assertIn("diabetes insipidus", prompt)
        self.assertIn("rewriter", system_prompt.lower())

    @patch("backend.rag_pipeline.get_provider")
    def test_new_unrelated_topic_left_unchanged(self, mock_get_provider):
        """
        When the follow-up is clearly a new unrelated topic, the AI should
        return the original query unchanged. We mock it to confirm the
        prompt's instruction is followed.
        """
        mock_get_provider.return_value = self._mock_provider(
            "what is the treatment for rheumatoid arthritis"
        )

        from backend.rag_pipeline import _rewrite_query

        result = self._run_async(_rewrite_query(
            query="what is the treatment for rheumatoid arthritis",
            context={
                "previousQuery": "diabetes symptoms",
                "previousAnswer": (
                    "Based on the retrieved evidence, diabetes insipidus is a "
                    "condition characterized by polydipsia and polyuria."
                ),
            },
        ))

        # Should return the original query since it's a new topic
        self.assertEqual(result, "what is the treatment for rheumatoid arthritis")

    @patch("backend.rag_pipeline.get_provider")
    def test_fallback_when_provider_fails(self, mock_get_provider):
        """
        If the AI provider raises an exception, _rewrite_query should
        gracefully fall back to the original query.
        """
        mock_get_provider.side_effect = Exception("API key not configured")

        from backend.rag_pipeline import _rewrite_query

        result = self._run_async(_rewrite_query(
            query="what ages does it happen to",
            context={
                "previousQuery": "diabetes symptoms",
                "previousAnswer": "Diabetes insipidus causes excessive thirst.",
            },
        ))

        self.assertEqual(result, "what ages does it happen to")

    @patch("backend.rag_pipeline.get_provider")
    def test_fallback_when_provider_returns_empty(self, mock_get_provider):
        """
        If the provider returns empty text, fall back to original query.
        """
        mock_get_provider.return_value = self._mock_provider("")

        from backend.rag_pipeline import _rewrite_query

        result = self._run_async(_rewrite_query(
            query="what ages does it happen to",
            context={
                "previousQuery": "diabetes symptoms",
                "previousAnswer": "Diabetes insipidus causes excessive thirst.",
            },
        ))

        self.assertEqual(result, "what ages does it happen to")

    @patch("backend.rag_pipeline.get_provider")
    def test_empty_context_does_not_crash(self, mock_get_provider):
        """
        When context is empty (no previousQuery / previousAnswer), the
        function should not crash and should return a valid string.
        """
        mock_get_provider.return_value = self._mock_provider(
            "diabetes insipidus age of onset"
        )

        from backend.rag_pipeline import _rewrite_query

        # Empty dict context means no previous content — function still works
        result = self._run_async(_rewrite_query(
            query="what ages does it happen to",
            context={},
        ))

        # Should still succeed (AI gets empty context, rewrites based on query alone)
        self.assertEqual(result, "diabetes insipidus age of onset")

    @patch("backend.rag_pipeline.get_provider")
    def test_run_pipeline_skips_rewrite_when_context_none(self, mock_get_provider):
        """
        run_pipeline should NOT call _rewrite_query when context is None.
        The original query should go straight to PubMed.
        """
        from backend.rag_pipeline import run_pipeline

        # Mock search_pubmed to return empty so we don't hit real APIs
        with patch("backend.rag_pipeline.search_pubmed", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            # Use a unique query so we can verify what Pubmed receives
            result = self._run_async(run_pipeline(
                query="unique_test_query_diabetes_symptoms",
                confidence="medium",
                context=None,  # No context — should skip rewriting
            ))

            # Verify search_pubmed was called with the ORIGINAL query
            mock_search.assert_called_once()
            call_args, _ = mock_search.call_args
            self.assertIn("unique_test_query_diabetes_symptoms", str(call_args))

        # get_provider should NOT have been called (no rewriting happened)
        mock_get_provider.assert_not_called()

    @patch("backend.rag_pipeline.get_provider")
    def test_quotes_stripped_from_rewritten_query(self, mock_get_provider):
        """
        The function strips quotation marks from the AI's response, since
        some models wrap the output in quotes despite instructions.
        """
        mock_get_provider.return_value = self._mock_provider(
            '"diabetes insipidus age of onset"'
        )

        from backend.rag_pipeline import _rewrite_query

        result = self._run_async(_rewrite_query(
            query="what ages does it happen to",
            context={
                "previousQuery": "diabetes symptoms",
                "previousAnswer": "Diabetes insipidus causes polydipsia and polyuria.",
            },
        ))

        self.assertEqual(result, "diabetes insipidus age of onset")


if __name__ == "__main__":
    unittest.main()
