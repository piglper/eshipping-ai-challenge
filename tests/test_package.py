import re

import eshipping_ai


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", eshipping_ai.__version__)
