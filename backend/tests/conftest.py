import os
import tempfile

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ORVYN_DATA_DIR", tempfile.mkdtemp(prefix="orvyn-test-data-"))

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.database.db import init_db


@pytest.fixture(scope="session")
def client():
    init_db()
    app = create_app()
    with TestClient(app) as tc:
        yield tc


@pytest.fixture()
def png_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 32), color=(120, 20, 200)).save(buf, format="PNG")
    return buf.getvalue()
