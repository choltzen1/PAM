"""Unit tests for the ai/ module. All tests use mocks — no real Azure OpenAI calls."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestAIClient:
    """Tests for ai/client.py."""

    def test_is_ai_available_returns_false_without_env(self):
        """AI should be unavailable when env vars are missing."""
        # Reset the singleton so it re-checks env
        import ai.client as client_mod
        client_mod._client = None
        with patch.dict('os.environ', {}, clear=True):
            assert client_mod.is_ai_available() is False

    def test_get_deployment_name_default(self):
        from ai.client import get_deployment_name
        with patch.dict('os.environ', {}, clear=True):
            assert get_deployment_name() == 'gpt-4o-mini'

    def test_get_deployment_name_from_env(self):
        from ai.client import get_deployment_name
        with patch.dict('os.environ', {'AZURE_OPENAI_DEPLOYMENT': 'my-deploy'}):
            assert get_deployment_name() == 'my-deploy'


class TestTools:
    """Tests for ai/tools.py."""

    def test_truncate_df_none(self):
        from ai.tools import _truncate_df
        assert _truncate_df(None) == "No data found."

    def test_truncate_df_empty(self):
        from ai.tools import _truncate_df
        assert _truncate_df(pd.DataFrame()) == "No data found."

    def test_truncate_df_caps_at_max_rows(self):
        from ai.tools import _truncate_df
        df = pd.DataFrame({'a': range(100), 'b': range(100)})
        result = _truncate_df(df, max_rows=10)
        assert 'showing 10 of 100' in result

    def test_truncate_df_small_no_truncation(self):
        from ai.tools import _truncate_df
        df = pd.DataFrame({'x': [1, 2, 3]})
        result = _truncate_df(df, max_rows=10)
        assert 'showing' not in result
        assert '1' in result

    def test_format_promo_dict_none(self):
        from ai.tools import _format_promo_dict
        assert _format_promo_dict(None) == "Promo not found."

    def test_format_promo_dict_with_data(self):
        from ai.tools import _format_promo_dict
        promo = {'code': 'R160', 'owner': 'John', 'bill_facing_name': 'Test Promo'}
        result = _format_promo_dict(promo)
        assert 'R160' in result
        assert 'John' in result

    def test_build_pete_handlers_returns_all_tools(self):
        from ai.tools import build_pete_handlers
        dm = MagicMock()
        svc = MagicMock()
        handlers = build_pete_handlers(dm, svc)
        expected = {
            'get_promo_eligibility', 'get_promo_details', 'get_promo_error_reasons',
            'get_rate_plan_data', 'get_active_aal_lines', 'search_promos', 'compare_promos',
        }
        assert set(handlers.keys()) == expected

    def test_handler_get_promo_details_calls_data_manager(self):
        from ai.tools import build_pete_handlers
        dm = MagicMock()
        dm.get_promo.return_value = {'code': 'R160', 'owner': 'Test'}
        svc = MagicMock()
        handlers = build_pete_handlers(dm, svc)
        result = handlers['get_promo_details'](promo_code='r160')
        dm.get_promo.assert_called_once_with('R160')
        assert 'R160' in result

    def test_handler_search_promos_no_results(self):
        from ai.tools import build_pete_handlers
        dm = MagicMock()
        dm.get_paginated_promos.return_value = {'promos': []}
        svc = MagicMock()
        handlers = build_pete_handlers(dm, svc)
        result = handlers['search_promos'](search_term='nonexistent')
        assert 'No promotions found' in result

    def test_handler_compare_promos_missing(self):
        from ai.tools import build_pete_handlers
        dm = MagicMock()
        dm.get_promo.return_value = None
        svc = MagicMock()
        handlers = build_pete_handlers(dm, svc)
        result = handlers['compare_promos'](promo_code_a='R999', promo_code_b='S999')
        assert 'not found' in result


class TestChat:
    """Tests for ai/chat.py."""

    def test_build_session_context_empty(self):
        from ai.chat import _build_session_context
        ctx = _build_session_context({})
        assert 'No session data' in ctx

    def test_build_session_context_with_eip_ban(self):
        from ai.chat import _build_session_context
        ctx = _build_session_context({
            'eip_id': '1234567890',
            'used_ban': '123456789',
            'promo_code': 'R160',
        })
        assert '1234567890' in ctx
        assert '123456789' in ctx
        assert 'R160' in ctx

    def test_build_session_context_truncates_long_data(self):
        from ai.chat import _build_session_context, MAX_CONTEXT_CHARS
        long_data = 'x' * 20000
        ctx = _build_session_context({'eligibility_summary': long_data})
        # The eligibility portion should be capped
        assert len(ctx) < 20000

    def test_trim_history_preserves_system(self):
        from ai.chat import _trim_history
        messages = [
            {"role": "system", "content": "system prompt"},
            *[{"role": "user", "content": f"msg {i}"} for i in range(50)],
        ]
        trimmed = _trim_history(messages, max_messages=10)
        assert trimmed[0]['role'] == 'system'
        assert len(trimmed) == 11  # 1 system + 10 kept

    def test_pete_chat_completion_returns_empty_when_unavailable(self):
        """Should return empty string when AI client is None, signaling fallback."""
        import ai.client as client_mod
        client_mod._client = None
        with patch.dict('os.environ', {}, clear=True):
            from ai.chat import pete_chat_completion
            result = pete_chat_completion("hello", [], {}, {})
            assert result == ""
