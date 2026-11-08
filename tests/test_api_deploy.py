"""api.deploy: the built web app on the same origin, and the optional shared password."""
import base64

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deploy import BasicAuthMiddleware, mount_web


def _app(tmp_path, password=None):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>radar</html>")
    (tmp_path / "assets" / "app.js").write_text("js")
    (tmp_path / "logo.png").write_bytes(b"png")
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"ok": True}
    if password:
        app.add_middleware(BasicAuthMiddleware, password=password)
    assert mount_web(app, tmp_path)
    return TestClient(app)


def test_spa_routes_and_static_files(tmp_path):
    c = _app(tmp_path)
    assert c.get("/").text == "<html>radar</html>" and c.get("/assistant").text == "<html>radar</html>"
    assert c.get("/assets/app.js").text == "js" and c.get("/logo.png").content == b"png"
    assert c.get("/api/nope").status_code == 404 and c.get("/api/health").json() == {"ok": True}


def test_no_dist_mounts_nothing(tmp_path):
    assert mount_web(FastAPI(), tmp_path / "missing") is False


def test_password_gate(tmp_path):
    c = _app(tmp_path, password="s3cret")
    auth = lambda pw: {"Authorization": "Basic " + base64.b64encode(f"x:{pw}".encode()).decode()}
    assert c.get("/").status_code == 401 and c.get("/", headers=auth("wrong")).status_code == 401
    assert c.get("/", headers=auth("s3cret")).status_code == 200
    assert c.get("/api/health").status_code == 200                       # the host's health check stays open
