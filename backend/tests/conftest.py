import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _dispose_engines():
    yield
    from alphalab_store.database import dispose_session_factories

    dispose_session_factories()
