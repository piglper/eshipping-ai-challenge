"""Contract of ``LLMClient`` for the Ollama adapter.

A small HTTP server plays Ollama, so the test runs anywhere. With
``ESHIPPING_OLLAMA_MODEL=<model>`` the same request also goes to a real local Ollama.
"""

import json
import os
import socketserver
import threading
from collections.abc import Iterator
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest

from eshipping_ai.adapters.ollama_client import OllamaClient
from eshipping_ai.domain.ports import LLMError
from eshipping_ai.extraction.llm_extractor import build_request

REQUEST = build_request(
    "Asunto: Salida BKG 990000101\nEl buque AURORA FICTICIA sale el 08/10/2026.",
    ("vessel", "vessel_departure"),
    date(2026, 9, 20),
)


class FakeOllama(BaseHTTPRequestHandler):
    answer: ClassVar[str] = json.dumps({"facts": []})
    received: ClassVar[list[dict[str, Any]]] = []
    imposed_schema: ClassVar[bool] = True

    def do_GET(self) -> None:
        self._send({"models": [{"name": "fake:1b"}]})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.received.append(body)
        if "format" in body and not FakeOllama.imposed_schema:
            self._send({"error": "structured output is unavailable"}, status=501)
            return
        self._send(
            {
                "model": body["model"],
                "message": {"role": "assistant", "content": FakeOllama.answer},
                "prompt_eval_count": 120,
                "eval_count": 15,
                "total_duration": 250_000_000,
            }
        )

    def _send(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        return None


class LocalServer(HTTPServer):
    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)  # skips the slow reverse DNS lookup
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


@pytest.fixture
def server() -> Iterator[str]:
    httpd = LocalServer(("127.0.0.1", 0), FakeOllama)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    FakeOllama.received.clear()
    FakeOllama.answer = json.dumps({"facts": []})
    FakeOllama.imposed_schema = True
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def test_a_call_imposes_the_schema_and_temperature_zero(server: str) -> None:
    response = OllamaClient("fake:1b", server).complete(REQUEST)
    (body,) = FakeOllama.received
    assert body["format"] == REQUEST.json_schema and body["options"]["temperature"] == 0
    assert body["stream"] is False
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert response.output == {"facts": []}
    assert (response.input_tokens, response.output_tokens, response.latency_ms) == (120, 15, 250)


def test_examples_go_before_the_message(server: str) -> None:
    request = REQUEST.model_copy(update={"examples": (("in", "out"),)})
    OllamaClient("fake:1b", server).complete(request)
    roles = [m["role"] for m in FakeOllama.received[0]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_availability_needs_the_server_and_the_model(server: str) -> None:
    assert OllamaClient("fake:1b", server).available()
    assert not OllamaClient("other:7b", server).available()
    assert not OllamaClient("fake:1b", "http://127.0.0.1:9").available()


def test_a_model_without_imposed_schema_gets_it_in_the_instructions(server: str) -> None:
    FakeOllama.imposed_schema = False
    FakeOllama.answer = 'Sure! {"facts": []} Hope it helps.'
    client = OllamaClient("fake:1b", server)
    assert client.complete(REQUEST).output == {"facts": []}
    assert client.complete(REQUEST).output == {"facts": []}
    first, second, third = FakeOllama.received
    assert "format" in first and "format" not in second and "format" not in third
    assert "follows this schema" in second["messages"][0]["content"]


def test_a_bare_list_is_put_back_under_the_only_list_property(server: str) -> None:
    fact = {"field": "vessel", "value": "AURORA FICTICIA", "classifier": "EST", "quote": "x"}
    FakeOllama.answer = json.dumps([fact])
    assert OllamaClient("fake:1b", server).complete(REQUEST).output == {"facts": [fact]}


@pytest.mark.parametrize("answer", ["not json", '"just a string"'])
def test_an_answer_that_is_not_a_json_object_is_an_error(server: str, answer: str) -> None:
    FakeOllama.answer = answer
    with pytest.raises(LLMError):
        OllamaClient("fake:1b", server).complete(REQUEST)


def test_an_unreachable_server_is_an_error() -> None:
    with pytest.raises(LLMError):
        OllamaClient("fake:1b", "http://127.0.0.1:9", timeout_s=1).complete(REQUEST)


@pytest.mark.skipif(
    not os.environ.get("ESHIPPING_OLLAMA_MODEL"), reason="needs a local Ollama model"
)
def test_a_real_model_answers_with_the_schema() -> None:
    client = OllamaClient(os.environ["ESHIPPING_OLLAMA_MODEL"])
    assert client.available()
    response = client.complete(REQUEST)
    assert isinstance(response.output.get("facts"), list)


def test_a_bare_list_is_an_error_when_the_schema_has_no_single_list() -> None:
    request = REQUEST.model_copy(
        update={"json_schema": {"type": "object", "properties": {"a": {}, "b": {}}}}
    )
    with pytest.raises(LLMError):
        OllamaClient._json_object("[1, 2]", request.json_schema)
