"""Object store on a local folder, with keys derived from the content hash."""

import hashlib
from pathlib import Path

_KEY_PARTS = 4


class LocalObjectStore:
    """Stores content under ``sha256/ab/cd/<digest>``: the same content is stored once."""

    def __init__(self, root: Path) -> None:
        """Create a store.

        Args:
            root: Folder that holds the objects; created on first write.
        """
        self._root = root

    def put(self, content: bytes) -> str:
        """Store content and return its key."""
        digest = hashlib.sha256(content).hexdigest()
        key = f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"
        path = self._root / key
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return key

    def get(self, key: str) -> bytes:
        """Return the content stored under a key.

        Raises:
            KeyError: If the key is not valid or nothing is stored under it.
        """
        parts = key.split("/")
        if parts[0] != "sha256" or len(parts) != _KEY_PARTS or ".." in parts:
            raise KeyError(key)
        path = self._root / key
        if not path.is_file():
            raise KeyError(key)
        return path.read_bytes()
