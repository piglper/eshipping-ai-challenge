"""``LLMClient`` for tests and for runs without a model: scripted answers, no network."""

from collections.abc import Callable, Mapping

from eshipping_ai.domain.ports import LLMError, LLMRequest, LLMResponse

Script = Callable[[LLMRequest], Mapping[str, object]]


class FakeLLMClient:
    """Answers with a script and records every request it receives."""

    def __init__(self, script: Script | None = None, *, fail: bool = False) -> None:
        """Create a fake model.

        Args:
            script: Function from the request to the JSON answer; no facts if omitted.
            fail: Raise ``LLMError`` on every call, as an unreachable server would.
        """
        self._script = script or (lambda _: {"facts": []})
        self._fail = fail
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return the scripted answer."""
        self.requests.append(request)
        if self._fail:
            msg = "fake model configured to fail"
            raise LLMError(msg)
        return LLMResponse(
            output=self._script(request),
            model="fake",
            input_tokens=len(request.instructions + request.content) // 4,
            output_tokens=10,
            latency_ms=0,
        )
