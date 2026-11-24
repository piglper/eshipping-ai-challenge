"""The ports are protocols: a minimal fake must satisfy them structurally."""

from collections.abc import Sequence
from datetime import UTC, datetime

from eshipping_ai.domain.model import ErpRecord, ErpSnapshot
from eshipping_ai.domain.ports import Clock, ERPGateway, LLMClient, LLMRequest, LLMResponse


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 10, tzinfo=UTC)


class EchoLLM:
    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            output={"echo": request.content},
            model="fake",
            input_tokens=1,
            output_tokens=1,
            latency_ms=0,
        )


class EmptyErp:
    def read(self) -> tuple[ErpSnapshot, Sequence[ErpRecord]]:
        snapshot = ErpSnapshot(
            snapshot_id="s-1",
            read_at=FixedClock().now(),
            source="synthetic.csv",
            sha256="0" * 64,
            row_count=0,
        )
        return snapshot, []


def test_fakes_satisfy_the_ports() -> None:
    clock: Clock = FixedClock()
    llm: LLMClient = EchoLLM()
    erp: ERPGateway = EmptyErp()
    request = LLMRequest(prompt_version="p1", instructions="x", content="hola", json_schema={})
    assert llm.complete(request).output == {"echo": "hola"}
    assert erp.read()[0].row_count == 0
    assert clock.now().tzinfo is UTC
