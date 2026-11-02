"""LLM client wrapper.

Uses LiteLLM so any provider works: OpenAI, Anthropic, Mistral, Azure, or a local Ollama model
("ollama/llama3.1"). Install with `pip install surveyqa[llm]`.

Responses are cached on disk by a hash of (model, prompt) so re-runs after small edits are cheap.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, model: str, cache_dir: str | Path | None = ".surveyqa_cache",
                 temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # Subclasses / tests can override this single method.
    def _complete(self, system: str, user: str) -> str:
        try:
            import litellm
        except ImportError as e:  # pragma: no cover
            raise LLMError("LLM checks need litellm: pip install 'surveyqa[llm]'") from e
        resp = litellm.completion(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, user: str) -> dict | list:
        key = hashlib.sha256(f"{self.model}\n{system}\n{user}".encode()).hexdigest()
        cached = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if cached and cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        raw = self._complete(system, user)
        data = parse_json(raw)
        if cached:
            cached.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data


def parse_json(raw: str) -> dict | list:
    """Parse JSON from a model reply, tolerating ```json fences and leading prose."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    raise LLMError(f"Model did not return valid JSON: {raw[:200]!r}")
