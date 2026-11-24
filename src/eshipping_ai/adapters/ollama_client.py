"""``LLMClient`` on a local Ollama server (ADR-0005): nothing leaves the machine.

One call to ``/api/chat`` with the JSON schema imposed through ``format``, temperature 0
and a context sized for clean messages. Some models cannot have a schema imposed (Ollama
answers 501); for them the schema goes into the instructions and the JSON object is taken
from the answer. Either way the answer is checked by the extractor, which trusts nothing
of it. Only the standard library is used.
"""

import json
import re
import time
import urllib.error
import urllib.request

from eshipping_ai.domain.ports import LLMError, LLMRequest, LLMResponse

DEFAULT_URL = "http://localhost:11434"
_NANOSECONDS_PER_MS = 1_000_000
_NOT_IMPLEMENTED = 501
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class _SchemaUnavailableError(Exception):
    """The model cannot have a JSON schema imposed."""


class OllamaClient:
    """Structured-output calls to a model served by Ollama."""

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_URL,
        *,
        num_ctx: int = 8192,
        timeout_s: float = 120.0,
    ) -> None:
        """Create a client.

        Args:
            model: Name of the model in Ollama (for example ``qwen3.5:4b``).
            base_url: Address of the Ollama server.
            num_ctx: Context window, sized to the longest clean message expected.
            timeout_s: Time allowed for one call.
        """
        self._model = model
        self._url = base_url.rstrip("/")
        self._num_ctx = num_ctx
        self._timeout = timeout_s
        self._imposed_schema = True

    def _post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(  # noqa: S310 - the URL is configuration, not input
            f"{self._url}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as answer:  # noqa: S310
                result: dict[str, object] = json.loads(answer.read())
        except urllib.error.HTTPError as error:
            if error.code == _NOT_IMPLEMENTED and b"structured output" in error.read():
                raise _SchemaUnavailableError from error
            msg = f"ollama call failed: {error}"
            raise LLMError(msg) from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            msg = f"ollama call failed: {error}"
            raise LLMError(msg) from error
        return result

    def available(self) -> bool:
        """Tell whether the server answers and has the model."""
        try:
            with urllib.request.urlopen(f"{self._url}/api/tags", timeout=5) as answer:  # noqa: S310
                models = json.loads(answer.read()).get("models", [])
        except urllib.error.URLError, TimeoutError, json.JSONDecodeError:
            return False
        return any(item.get("name") == self._model for item in models)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one call; the answer is a JSON object meant to follow the request schema.

        Raises:
            LLMError: If the server does not answer or the answer is not a JSON object.
        """
        started = time.monotonic()
        if self._imposed_schema:
            try:
                result = self._post("/api/chat", self._body(request, imposed=True))
            except _SchemaUnavailableError:
                self._imposed_schema = False
        if not self._imposed_schema:
            result = self._post("/api/chat", self._body(request, imposed=False))
        message = result.get("message")
        content = str(message.get("content", "")) if isinstance(message, dict) else ""
        duration = result.get("total_duration")
        return LLMResponse(
            output=self._json_object(content),
            model=str(result.get("model", self._model)),
            input_tokens=int(str(result.get("prompt_eval_count", 0))),
            output_tokens=int(str(result.get("eval_count", 0))),
            latency_ms=(
                int(str(duration)) // _NANOSECONDS_PER_MS
                if duration
                else int((time.monotonic() - started) * 1000)
            ),
        )

    def _body(self, request: LLMRequest, *, imposed: bool) -> dict[str, object]:
        instructions = request.instructions
        if not imposed:
            schema = json.dumps(dict(request.json_schema))
            instructions += (
                f"\nAnswer only with one JSON object that follows this schema:\n{schema}"
            )
        messages: list[dict[str, str]] = [{"role": "system", "content": instructions}]
        for example_input, example_output in request.examples:
            messages += [
                {"role": "user", "content": example_input},
                {"role": "assistant", "content": example_output},
            ]
        messages.append({"role": "user", "content": request.content})
        body: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": self._num_ctx},
        }
        if imposed:
            body["format"] = dict(request.json_schema)
        return body

    @staticmethod
    def _json_object(content: str) -> dict[str, object]:
        """The JSON object of an answer, also when the model wraps it in other text."""
        for candidate in (content, *(m.group(0) for m in [_JSON_OBJECT_RE.search(content)] if m)):
            try:
                output = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(output, dict):
                return output
        msg = "the model did not answer with a JSON object"
        raise LLMError(msg)
