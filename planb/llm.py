"""Provider-agnostic LLM client (OpenAI-compatible) with disk cache and mock mode.

Works with any OpenAI-compatible endpoint, which covers most FREE / open-model
options: Groq, OpenRouter (":free" models), SiliconFlow, Together, local Ollama
(http://localhost:11434/v1), vLLM, LM Studio ...

Configuration (.env or environment variables):
  LLM_PROVIDER   openai_compatible | mock          (default: mock if no key/base url)
  LLM_BASE_URL   e.g. https://api.groq.com/openai/v1
  LLM_API_KEY    your key (never commit it)
  LLM_MODEL      e.g. llama-3.3-70b-versatile / Qwen/Qwen2.5-7B-Instruct / qwen2.5:7b

Every real response is cached under .cache/llm/ keyed by (model, messages,
temperature) so experiments are reproducible and free-tier quota is not wasted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:  # pragma: no cover - dotenv is optional
    pass

CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "llm"


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False
    model: str = ""
    provider: str = ""


@dataclass
class LLMUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0

    def add(self, r: LLMResponse) -> None:
        self.calls += 1
        self.prompt_tokens += r.prompt_tokens
        self.completion_tokens += r.completion_tokens
        self.latency_s += r.latency_s


class LLMClient:
    def __init__(self, provider: str | None = None, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, temperature: float = 0.0, use_cache: bool = True,
                 max_retries: int = 3):
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "mock")
        default_provider = "openai_compatible" if (self.api_key or self.base_url) else "mock"
        self.provider = provider or os.getenv("LLM_PROVIDER", default_provider)
        if self.provider == "mock":
            self.model = "mock"
        self.temperature = temperature
        self.use_cache = use_cache
        self.max_retries = max_retries
        self._client = None

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    def describe(self) -> str:
        return "mock (no LLM)" if self.is_mock else f"{self.model} @ {self.base_url or 'default'}"

    def _cache_path(self, messages: list[dict], max_tokens: int) -> Path:
        key = json.dumps({"m": self.model, "u": self.base_url, "msgs": messages, "t": self.temperature,
                          "mt": max_tokens}, ensure_ascii=False, sort_keys=True)
        return CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()}.json"

    def chat(self, messages: list[dict], max_tokens: int = 1500,
             mock: Optional[Callable[[list[dict]], str]] = None) -> LLMResponse:
        if self.is_mock:
            t0 = time.perf_counter()
            text = mock(messages) if mock else ""
            return LLMResponse(text=text, latency_s=time.perf_counter() - t0, model="mock", provider="mock")

        # reasoning models spend completion tokens on hidden reasoning; LLM_MIN_MAX_TOKENS raises the budget
        max_tokens = max(max_tokens, int(os.environ.get("LLM_MIN_MAX_TOKENS", "0") or 0))
        path = self._cache_path(messages, max_tokens)
        if self.use_cache and path.exists():
            data = json.loads(path.read_text())
            return LLMResponse(**{**data, "cached": True})

        if self._client is None:
            from openai import OpenAI

            # max_retries=0: retries are handled below, so free-tier request quotas are not spent silently
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key or "not-needed", max_retries=0)
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                t0 = time.perf_counter()
                resp = self._client.chat.completions.create(
                    model=self.model, messages=messages, temperature=self.temperature, max_tokens=max_tokens)
                latency = time.perf_counter() - t0
                usage = resp.usage
                out = LLMResponse(text=resp.choices[0].message.content or "",
                                  prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                                  completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                                  latency_s=latency, model=self.model, provider=self.provider)
                if self.use_cache and out.text.strip():
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(out.__dict__, ensure_ascii=False))
                return out
            except Exception as e:  # rate limits on free tiers are common
                last_err = e
                msg = str(e).lower()
                if "per-day" in msg or "per day" in msg or "daily" in msg:
                    raise RuntimeError(f"Daily request quota exhausted: {e}") from e
                time.sleep(min(30, 2 ** (attempt + 2)))
        raise RuntimeError(f"LLM call failed after {self.max_retries} attempts: {last_err}")


def extract_json(text: str) -> Optional[dict]:
    """Best-effort extraction of the first JSON object in a model reply."""
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # reasoning models
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates = [fence.group(1)] if fence else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    return None
