import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import settings

from eshipping_ai.domain.model import Document, Mail, Message
from eshipping_ai.synthetic.build import build
from eshipping_ai.synthetic.spec import load_spec

SPEC_PATH = Path(__file__).parents[1] / "data_sample" / "spec" / "sample.yaml"

# Property tests: a quick default run and a thorough one (HYPOTHESIS_PROFILE=thorough).
settings.register_profile("default", max_examples=100, deadline=None)
settings.register_profile("thorough", max_examples=5000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark as integration every test that runs on the generated synthetic data set."""
    for item in items:
        if "synthetic_dir" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)


class MemoryInbox:
    """In-memory ``InboxStore``: mails, messages (once per hash) and documents (once per hash)."""

    def __init__(self) -> None:
        self.mails: dict[str, Mail] = {}
        self.messages: dict[str, Message] = {}
        self.links: list[tuple[str, str, int]] = []
        self.documents: dict[str, Document] = {}
        self.document_links: list[tuple[str, str]] = []

    def add_mail(self, mail: Mail) -> bool:
        if mail.mail_id in self.mails:
            return False
        self.mails[mail.mail_id] = mail
        return True

    def add_message(self, message: Message, mail_id: str, depth: int) -> bool:
        self.links.append((mail_id, message.message_id, depth))
        if message.content_hash in self.messages:
            return False
        self.messages[message.content_hash] = message
        return True

    def add_document(self, document: Document, message_id: str) -> bool:
        self.document_links.append((message_id, document.document_id))
        if document.sha256 in self.documents:
            return False
        self.documents[document.sha256] = document
        return True


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


@pytest.fixture
def inbox() -> MemoryInbox:
    return MemoryInbox()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture(scope="session")
def synthetic_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The synthetic data set, generated once per test session."""
    out = tmp_path_factory.mktemp("synthetic")
    build(load_spec(SPEC_PATH), out)
    return out
