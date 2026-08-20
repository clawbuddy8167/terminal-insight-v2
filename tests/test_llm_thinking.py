"""LLM provider: DeepSeek thinking mode for vote."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from pydantic import BaseModel

from terminal_insight_v2.config import Settings
from terminal_insight_v2.providers.llm import LLMProvider


def test_complete_passes_thinking_params_when_enabled():
    settings = Settings(_env_file=None, openai_api_key="test-key")
    provider = LLMProvider(settings, thinking_enabled=True)
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"ok": true}', reasoning_content="chain"),
                finish_reason="stop",
            )
        ]
    )
    provider._client = mock_client

    text, finish = provider._complete(
        "sys",
        "user",
        temperature=0.2,
        max_tokens=1024,
        use_json_object=True,
        thinking=True,
    )

    assert text == '{"ok": true}'
    assert finish == "stop"
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert kwargs["response_format"] == {"type": "json_object"}


def test_complete_omits_thinking_params_by_default():
    settings = Settings(_env_file=None, openai_api_key="test-key")
    provider = LLMProvider(settings)
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"ok": true}'),
                finish_reason="stop",
            )
        ]
    )
    provider._client = mock_client

    provider._complete(
        "sys",
        "user",
        temperature=0.2,
        max_tokens=1024,
        use_json_object=False,
        thinking=False,
    )

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "reasoning_effort" not in kwargs
    assert "extra_body" not in kwargs


def test_chat_json_thinking_bumps_tokens_on_empty_length():
    """Thinking can exhaust max_tokens → empty content; must retry with a larger budget."""

    class Payload(BaseModel):
        ok: bool

    settings = Settings(_env_file=None, openai_api_key="test-key")
    provider = LLMProvider(settings, thinking_enabled=True)
    seen_max: list[int] = []

    def fake_complete(system, user, *, temperature, max_tokens, use_json_object, thinking):
        seen_max.append(max_tokens)
        if len(seen_max) == 1:
            return "", "length"
        return '{"ok": true}', "stop"

    provider._complete = fake_complete  # type: ignore[method-assign]
    out = provider.chat_json("sys", "user", Payload, max_tokens=2048, parse_retries=3)
    assert out.ok is True
    assert seen_max[0] >= 8192  # thinking floor
    assert seen_max[1] > seen_max[0]
