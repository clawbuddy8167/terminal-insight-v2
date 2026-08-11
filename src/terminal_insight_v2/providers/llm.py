"""OpenAI-compatible LLM client."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Optional, Type, TypeVar

from openai import APIConnectionError, BadRequestError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from terminal_insight_v2.config import Settings

T = TypeVar("T", bound=BaseModel)


class LLMProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.call_count = 0
        self.retry_count = 0
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self.settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=self.settings.openai_timeout,
            )
        return self._client

    def chat_json(
        self,
        system: str,
        user: str,
        model: Type[T],
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        parse_retries: int = 3,
    ) -> T:
        last_err: Exception | None = None
        for attempt in range(max(1, parse_retries)):
            try:
                text, finish = self._complete(
                    system,
                    user,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_json_object=True,
                )
                if not (text or "").strip():
                    raise ValueError("empty LLM content")
                if finish == "length" and attempt + 1 < parse_retries:
                    self.retry_count += 1
                    max_tokens = min(8192, int(max_tokens * 1.5))
                    time.sleep(0.4 * (attempt + 1))
                    continue
                data = parse_json_payload(text)
                if data is None:
                    raise ValueError(f"LLM did not return valid JSON: {text[:240]}")
                return model.model_validate(data)
            except (RateLimitError, APIConnectionError) as exc:
                last_err = exc
                self.retry_count += 1
                time.sleep(min(12.0, 2.0 * (attempt + 1)))
            except (ValueError, ValidationError, BadRequestError, json.JSONDecodeError) as exc:
                last_err = exc
                self.retry_count += 1
                time.sleep(0.5 * (attempt + 1))
        raise last_err or ValueError("LLM chat_json failed")

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        max_tokens: int,
        use_json_object: bool,
    ) -> tuple[str, str]:
        client = self._get_client()
        self.call_count += 1
        sys_msg = system + "\n\n必须仅输出合法 JSON 对象，不要 Markdown，不要额外文本。"
        payload: dict[str, Any] = dict(
            model=self.settings.openai_model,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if use_json_object:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = client.chat.completions.create(**payload)
        except BadRequestError:
            payload.pop("response_format", None)
            resp = client.chat.completions.create(**payload)
        choice = resp.choices[0]
        return (choice.message.content or "").strip(), getattr(choice, "finish_reason", "") or ""


def sanitize_json_strings(text: str) -> str:
    if not text:
        return ""
    out: list[str] = []
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
    return "".join(out)


def parse_json_payload(text: str) -> Any:
    if not (text or "").strip():
        return None
    for candidate in (text, repair_truncated_json(text)):
        if not candidate:
            continue
        data = extract_json_object(candidate, "dict")
        if data is not None:
            return data
        data = extract_json_object(sanitize_json_strings(candidate), "dict")
        if data is not None:
            return data
    return None


def extract_json_object(text: str, json_type: str = "dict") -> Any:
    if not text:
        return None
    raw = text.strip().lstrip("\ufeff")
    cleaned = re.sub(r"(?m)^\s*(//|#).*?$", "", raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    code_block = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass
    return _balanced_extract(raw, json_type)


def repair_truncated_json(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    if s.endswith("\\"):
        s = s[:-1]
    in_str = esc = False
    stack: list[str] = []
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()
    if in_str:
        s += '"'
    s = re.sub(r"[,\s:]+$", "", s)
    while stack:
        s += stack.pop()
    return s


def _balanced_extract(text: str, json_type: str) -> Any:
    open_ch, close_ch = ("{", "}") if json_type == "dict" else ("[", "]")
    start = text.find(open_ch)
    while start != -1:
        depth = in_str = esc = 0
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        repaired = repair_truncated_json(text[start:])
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
        start = text.find(open_ch, start + 1)
    return None
