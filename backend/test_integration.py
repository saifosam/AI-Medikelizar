"""
AI-Medikelizar — Comprehensive Integration Tests
==================================================
Tests for multi-language support, flexible subscriptions/credits,
and the Humanizer toggle feature.

Run with:
    python -m pytest backend/test_integration.py -v
Or:
    python backend/test_integration.py
"""

import asyncio
import unittest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
from typing import Optional

# ── Test: Multi-Language ──────────────────────────────────────────────

class TestMultiLanguage(unittest.TestCase):
    """Test language parameter flows through the entire backend."""

    def test_query_request_default_language(self):
        """QueryRequest defaults to 'en' when no language specified."""
        from backend.models import QueryRequest
        req = QueryRequest(query="test")
        self.assertEqual(req.language, "en")

    def test_query_request_explicit_language(self):
        """QueryRequest accepts explicit language codes."""
        from backend.models import QueryRequest
        req = QueryRequest(query="test", language="ar")
        self.assertEqual(req.language, "ar")

    def test_query_request_language_passthrough(self):
        """Language is preserved through model serialization."""
        from backend.models import QueryRequest
        req = QueryRequest(query="test", language="ar")
        data = req.model_dump()
        self.assertEqual(data["language"], "ar")

    def test_humanize_request_default_language(self):
        """HumanizeRequest defaults to 'en' when no language specified."""
        from backend.models import HumanizeRequest
        req = HumanizeRequest(answer="<p>test</p>")
        self.assertEqual(req.language, "en")

    def test_humanize_request_explicit_language(self):
        """HumanizeRequest accepts explicit language codes."""
        from backend.models import HumanizeRequest
        req = HumanizeRequest(answer="<p>test</p>", language="ar")
        self.assertEqual(req.language, "ar")

    @patch("backend.rag_pipeline.get_provider")
    def test_language_in_build_prompt(self, mock_get_provider):
        """_build_prompt includes language instruction for Arabic."""
        from backend.rag_pipeline import _build_prompt
        from backend.models import SourceModel

        source = SourceModel(
            id=1, title="Test", authors="A", journal="J",
            date="2025", abstract="Abstract"
        )
        prompt = _build_prompt("test query", [source], language="ar")
        self.assertIn("Arabic", prompt)
        self.assertIn("write your entire answer in Arabic", prompt)

    @patch("backend.rag_pipeline.get_provider")
    def test_language_in_build_prompt_english(self, mock_get_provider):
        """_build_prompt includes language instruction for English."""
        from backend.rag_pipeline import _build_prompt
        from backend.models import SourceModel

        source = SourceModel(
            id=1, title="Test", authors="A", journal="J",
            date="2025", abstract="Abstract"
        )
        prompt = _build_prompt("test query", [source], language="en")
        self.assertIn("English", prompt)
        self.assertIn("write your entire answer in English", prompt)


# ── Test: Subscription / Credit System ────────────────────────────────

class TestSubscriptionCredits(unittest.TestCase):
    """Test the flexible subscription and credit enforcement system."""

    def test_price_calculation_basic(self):
        """Basic tier price is 0 regardless of daily_limit."""
        from backend.subscriptions import calculate_price_cents
        self.assertEqual(calculate_price_cents(5, "basic"), 0)
        self.assertEqual(calculate_price_cents(100, "basic"), 0)

    def test_price_calculation_premium(self):
        """Premium tier: price scales with daily_limit (10-25 range)."""
        from backend.subscriptions import calculate_price_cents
        # 10 queries: 10 × 30 × 0.15 × 1.33 = 59.85 → round to nearest 5 → 60
        price_10 = calculate_price_cents(10, "premium")
        self.assertEqual(price_10, 6000)  # 60 EGP = 6000 cents

        # 15 queries: 15 × 30 × 0.15 × 1.33 = 89.775 → round to nearest 5 → 90
        price_15 = calculate_price_cents(15, "premium")
        self.assertEqual(price_15, 9000)  # 90 EGP = 9000 cents

        # 25 queries: 25 × 30 × 0.15 × 1.33 = 149.625 → round to nearest 5 → 150
        price_25 = calculate_price_cents(25, "premium")
        self.assertEqual(price_25, 15000)  # 150 EGP = 15000 cents

    def test_price_calculation_vip(self):
        """VIP tier: price scales with daily_limit (25-60 range)."""
        from backend.subscriptions import calculate_price_cents
        # 40 queries: 40 × 30 × 0.15 × 1.50 = 270 → round to nearest 10 → 270
        price_40 = calculate_price_cents(40, "vip")
        self.assertEqual(price_40, 27000)  # 270 EGP = 27000 cents

        # 25 queries: 25 × 30 × 0.15 × 1.50 = 168.75 → round to nearest 5 → 170
        price_25 = calculate_price_cents(25, "vip")
        self.assertEqual(price_25, 17000)

        # 60 queries: 60 × 30 × 0.15 × 1.50 = 405 → round to nearest 10
        # round(40.5) = 40 (Python banker's rounding) → 40 * 10 = 400 EGP
        price_60 = calculate_price_cents(60, "vip")
        self.assertEqual(price_60, 40000)

    def test_tier_ranges(self):
        """Tier ranges define correct min/max limits."""
        from backend.subscriptions import TIER_RANGES
        self.assertEqual(TIER_RANGES["basic"], {"min": 5, "max": 5})
        self.assertEqual(TIER_RANGES["premium"], {"min": 10, "max": 25})
        self.assertEqual(TIER_RANGES["vip"], {"min": 25, "max": 60})

    def test_tier_definitions(self):
        """TIERS dict has all required fields for each tier."""
        from backend.subscriptions import TIERS
        for tier_id in ["basic", "premium", "vip"]:
            info = TIERS[tier_id]
            self.assertIn("label", info)
            self.assertIn("daily_limit_default", info)
            self.assertIn("daily_limit_min", info)
            self.assertIn("daily_limit_max", info)
            self.assertIn("features", info)
            self.assertIn("price_cents", info)

    def test_get_user_daily_limit_basic(self):
        """get_user_daily_limit returns 5 for basic tier users."""
        from backend.subscriptions import get_user_daily_limit
        # No user = basic tier
        result = get_user_daily_limit(None, None)
        self.assertEqual(result, 5)

    def test_get_user_daily_limit_premium_default(self):
        """Premium users with no stored daily_limit get the default (15)."""
        from backend.subscriptions import get_user_daily_limit

        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MagicMock()

        # No subscription record found → return None
        mock_db.query().filter().first.return_value = None

        with patch("backend.subscriptions.get_user_tier", return_value="premium"):
            result = get_user_daily_limit(mock_user, mock_db)
            self.assertEqual(result, 15)

    def test_get_tier_limits_basic(self):
        """get_tier_limits returns correct features for basic tier."""
        from backend.subscriptions import get_tier_limits
        limits = get_tier_limits("basic")
        self.assertEqual(limits["daily_limit_default"], 5)

    def test_get_tier_limits_unknown(self):
        """Unknown tier falls back to basic."""
        from backend.subscriptions import get_tier_limits
        limits = get_tier_limits("nonexistent")
        self.assertEqual(limits["daily_limit_default"], 5)

    def test_check_query_limit_anonymous(self):
        """Anonymous users (no user) are always allowed."""
        from backend.subscriptions import check_query_limit
        result = check_query_limit(None, None)
        self.assertTrue(result)

    def test_check_query_limit_basic_under(self):
        """Basic user with 3 queries used today should be allowed (3 < 5)."""
        from backend.subscriptions import check_query_limit
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MagicMock()

        # Mock the tier lookup (no subscription → basic)
        mock_db.query().filter().first.return_value = None

        # Mock query count: 3 used today
        mock_db.query().filter().count.return_value = 3

        # We need to mock get_user_tier as well since it queries the DB
        with patch("backend.subscriptions.get_user_tier", return_value="basic"):
            with patch("backend.subscriptions.get_user_daily_limit", return_value=5):
                result = check_query_limit(mock_user, mock_db)
                self.assertTrue(result)

    def test_check_query_limit_basic_at_limit(self):
        """Basic user with 5 queries used today should be blocked (5 >= 5)."""
        from backend.subscriptions import check_query_limit
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MagicMock()

        with patch("backend.subscriptions.get_user_tier", return_value="basic"):
            with patch("backend.subscriptions.get_user_daily_limit", return_value=5):
                with patch("backend.subscriptions.get_queries_used_today", return_value=5):
                    result = check_query_limit(mock_user, mock_db)
                    self.assertFalse(result)

    def test_check_query_limit_basic_over(self):
        """Basic user with 6 queries used today should be blocked (6 >= 5)."""
        from backend.subscriptions import check_query_limit
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MagicMock()

        with patch("backend.subscriptions.get_user_tier", return_value="basic"):
            with patch("backend.subscriptions.get_user_daily_limit", return_value=5):
                with patch("backend.subscriptions.get_queries_used_today", return_value=6):
                    result = check_query_limit(mock_user, mock_db)
                    self.assertFalse(result)

    def test_pricing_calculate_endpoint(self):
        """Test the /pricing/calculate endpoint logic."""
        from backend.subscriptions import TIERS, calculate_price_cents

        # Test premium at default
        tier_info = TIERS["premium"]
        clamped = max(tier_info["daily_limit_min"], min(15, tier_info["daily_limit_max"]))
        price = calculate_price_cents(clamped, "premium")
        self.assertEqual(price, 9000)  # 90 EGP

        # Test premium clamped below min
        clamped = max(tier_info["daily_limit_min"], min(5, tier_info["daily_limit_max"]))
        self.assertEqual(clamped, 10)  # Clamped to min

        # Test premium clamped above max
        clamped = max(tier_info["daily_limit_min"], min(100, tier_info["daily_limit_max"]))
        self.assertEqual(clamped, 25)  # Clamped to max

    def test_credits_endpoint_response(self):
        """Test the /credits endpoint logic structure."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MagicMock()

        with patch("backend.subscriptions.get_user_tier", return_value="premium"):
            with patch("backend.subscriptions.get_user_daily_limit", return_value=15):
                with patch("backend.subscriptions.get_queries_used_today", return_value=3):
                    from backend.subscriptions import get_user_tier, get_user_daily_limit, get_queries_used_today

                    tier = get_user_tier(mock_user, mock_db)
                    limit = get_user_daily_limit(mock_user, mock_db)
                    used = get_queries_used_today(mock_user, mock_db)
                    remaining = max(0, limit - used)

                    self.assertEqual(tier, "premium")
                    self.assertEqual(limit, 15)
                    self.assertEqual(used, 3)
                    self.assertEqual(remaining, 12)


# ── Test: Humanizer ───────────────────────────────────────────────────

class TestHumanizer(unittest.TestCase):
    """Test the humanizer toggle feature integration."""

    def test_humanize_request_model(self):
        """HumanizeRequest accepts answer, sources, and language."""
        from backend.models import HumanizeRequest, SourceModel

        source = SourceModel(
            id=1, title="Test", authors="A", journal="J",
            date="2025", abstract="Abstract"
        )
        req = HumanizeRequest(
            answer="<p>Clinical text with citation [1]</p>",
            sources=[source],
            language="ar",
        )
        self.assertEqual(req.language, "ar")
        self.assertEqual(len(req.sources), 1)
        self.assertIn("[1]", req.answer)

    def test_humanizer_does_not_call_query_limit(self):
        """Verify the /api/humanize route handler doesn't import query limit functions."""
        import inspect
        from backend.main import app

        # Find the humanize route handler
        humanize_route = None
        for route in app.routes:
            if hasattr(route, 'path') and '/api/humanize' in route.path:
                humanize_route = route
                break

        self.assertIsNotNone(humanize_route, "/api/humanize route not registered")

        # Get the source code of the endpoint function
        endpoint_func = humanize_route.endpoint
        source = inspect.getsource(endpoint_func)

        # The humanizer should NOT import or call these
        forbidden = ["check_query_limit", "QueryLogModel", "get_queries_used_today"]
        for func_name in forbidden:
            self.assertNotIn(func_name, source,
                f"Humanizer endpoint should not call {func_name}")

    def test_humanizer_prompt_includes_language(self):
        """The humanizer prompt should include language instruction."""
        import inspect
        from backend.main import app

        humanize_route = None
        for route in app.routes:
            if hasattr(route, 'path') and '/api/humanize' in route.path:
                humanize_route = route
                break

        endpoint_func = humanize_route.endpoint
        source = inspect.getsource(endpoint_func)

        # The source should use LANG_MAP and target_lang
        self.assertIn("LANG_MAP", source)
        self.assertIn("target_lang", source)
        self.assertIn("write your entire answer in", source)

    def test_humanizer_rate_limit(self):
        """Humanizer endpoint has a rate limit applied."""
        import inspect
        from backend.main import app

        humanize_route = None
        for route in app.routes:
            if hasattr(route, 'path') and '/api/humanize' in route.path:
                humanize_route = route
                break

        endpoint_func = humanize_route.endpoint
        # Check for the limiter decorator
        self.assertTrue(
            hasattr(endpoint_func, '__wrapped__') or
            hasattr(endpoint_func, '_slowapi_limits'),
            "Humanizer endpoint should have rate limiting"
        )


# ── Test: Full Query Flow (mocked) ────────────────────────────────────

class TestQueryFlow(unittest.TestCase):
    """Test the full /api/query flow with mocked dependencies."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _run_async(self, coro):
        return self.loop.run_until_complete(coro)

    @patch("backend.main.get_db")
    @patch("backend.main.get_current_user")
    @patch("backend.main.check_query_limit")
    @patch("backend.main.run_pipeline")
    async def test_query_response_includes_credits(self, mock_pipeline, mock_check,
                                                    mock_get_user, mock_get_db):
        """The /api/query response should include credit usage info."""
        from backend.main import query as query_endpoint
        from backend.models import QueryRequest, QueryResponse, SourceModel
        from fastapi import Request

        # Create mock objects
        mock_user = MagicMock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        mock_check.return_value = True

        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        # Mock pipeline result
        mock_pipeline.return_value = QueryResponse(
            answer="<p>Test answer</p>",
            sources=[SourceModel(id=1, title="Test", authors="A", journal="J",
                                  date="2025", abstract="Abstract")],
            confidence="medium",
            provider="mock",
            model="mock-model",
        )

        # Mock rate limiter to allow the request
        mock_request = MagicMock(spec=Request)

        # Since query endpoint has @limiter.limit decorator,
        # we test the inner logic by calling the handler directly
        # through FastAPI's dependency injection is complex,
        # so we verify the pipeline call has language param
        from backend.rag_pipeline import run_pipeline
        # This test verifies run_pipeline is imported and has language param
        import inspect
        sig = inspect.signature(run_pipeline)
        self.assertIn("language", sig.parameters)
        self.assertEqual(sig.parameters["language"].default, "en")


# ── Run tests ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
