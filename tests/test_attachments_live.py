"""LIVE proof of the two §10 #1 build-ladder legs ("test, don't assume").

The §10 #1 ladder names exactly two legs to prove during the build, and this
file is that proof — run once per build, findings recorded in
``tests/log/attachments_findings_*.txt`` (+ ``_latest``):

  * **Leg A — the WSL-native write path.** For a WSL-internal project root
    (``\\\\wsl.localhost\\<distro>\\home\\…``) the ingest must stream bytes
    through ``wsl.exe -d <distro> -- bash -c 'mkdir -p … && cat > tmp && mv
    tmp final'`` (binary stdin), because plain Python writes over the UNC
    share are the researched slow/fragile path. Proven here against a real
    throwaway project inside the installed distro, including the researched
    ``wslpath -w`` edge cases: a filename with **spaces + unicode**, byte-
    fidelity (sha256 verified inside the distro AND after a Windows read of
    the ``wslpath -w`` output), the **installed distro name** appearing in the
    materialized UNC path, and a WSL-internal ``source_path`` ingest.
  * **Leg B — the asset-endpoint byte render.** ``POST /library/assets``
    (base64-JSON upload) then ``GET /assets/{id}/{filename}?cwd=…`` through a
    real in-process app client (FastAPI ``TestClient`` — full HTTP stack:
    routing, path params, headers, streaming) must return the exact bytes with
    the correct content-type; traversal shapes 404; the pre-existing
    ``/assets/agent-icons/{name}`` route keeps precedence. Bonus: one real
    ``uvicorn`` server on an ephemeral ``127.0.0.1`` port serves the same
    bytes over a real socket.

Needs a real Windows + WSL2 machine (leg A) — the hermetic contract lives in
``tests/test_attachments_unit.py``.
"""

import base64
import datetime
import hashlib
import json
import logging
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

# The sidecar runs with its own dir on sys.path (not the repo root).
_SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import attachments  # noqa: E402
import main  # noqa: E402

log = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent / "log"

# Binary payload with NULs + high bytes — byte fidelity, not text luck.
PAYLOAD = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 8 + b"\x00" * 64
SHA = hashlib.sha256(PAYLOAD).hexdigest()

# Spaces + unicode in one leaf name — the researched wslpath -w edge cases.
EDGE_NAME = "spaced ünïcode ✓ file.png"

_FINDINGS: list[str] = []


def _note(line: str) -> None:
    log.info(line)
    _FINDINGS.append(line)


@pytest.fixture(scope="module", autouse=True)
def _findings_record():
    """Write the durable findings record whatever happens (the spike-file
    convention — tests/log/ keeps the plain-language answers)."""
    yield
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    text = "\n".join(
        [f"§10 #1 attachment materialization — live findings ({stamp})", ""]
        + (_FINDINGS or ["(no findings recorded — did every test skip?)"])) + "\n"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / f"attachments_findings_{stamp}.txt").write_text(text, encoding="utf-8")
    (LOG_DIR / "attachments_findings_latest.txt").write_text(text, encoding="utf-8")


def _default_distro() -> str | None:
    """The installed default WSL distro (first row of ``wsl -l -q``)."""
    try:
        r = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    text = r.stdout.decode("utf-16-le", "ignore")
    names = [ln.replace("﻿", "").replace("\x00", "").strip()
             for ln in text.splitlines()]
    names = [n for n in names if n]
    return names[0] if names else None


@pytest.fixture(scope="module")
def wsl_project():
    """A throwaway WSL-INTERNAL project (created + removed inside the distro)."""
    distro = _default_distro()
    if not distro:
        pytest.skip("no WSL distro available")
    import shlex
    q = shlex.quote
    home = attachments._wsl_run(distro, "echo $HOME").decode("utf-8").strip()
    assert home.startswith("/")
    proj_wsl = f"{home}/.awl-attach-live-{uuid.uuid4().hex[:8]}"
    # A .git marker pins storage.project_root to the throwaway dir.
    attachments._wsl_run(distro, f"mkdir -p {q(proj_wsl + '/.git')}")
    cwd_unc = (rf"\\wsl.localhost\{distro}" + proj_wsl.replace("/", "\\"))
    _note(f"leg A: distro={distro!r} project={proj_wsl!r} cwd(UNC)={cwd_unc!r}")
    yield {"distro": distro, "proj_wsl": proj_wsl, "cwd": cwd_unc}
    try:
        attachments._wsl_run(distro, f"rm -rf {q(proj_wsl)}")
    except RuntimeError:
        pass


class TestWslNativeWriteLeg:
    """Leg A: ingest into a WSL-INTERNAL project store via the wsl.exe path."""

    def test_store_kind_detects_the_wsl_leg(self, wsl_project):
        kind = attachments.store_kind(wsl_project["cwd"])
        assert kind == ("wsl", wsl_project["distro"])
        _note(f"leg A: store_kind -> {kind} (WSL leg chosen automatically)")

    def test_wsl_native_write_with_spaces_and_unicode(self, wsl_project):
        distro, proj_wsl = wsl_project["distro"], wsl_project["proj_wsl"]
        rec = attachments.ingest_bytes(
            wsl_project["cwd"], EDGE_NAME, PAYLOAD,
            created_by="live-test", citation={"doc": "roadmap.md", "location": "§2"})
        assert rec["sha256"] == SHA and rec["size"] == len(PAYLOAD)

        final_wsl = f"{proj_wsl}/.awl-cc-dash/{rec['rel_path']}"
        # 1) Byte fidelity INSIDE the distro (the write really landed native).
        import shlex
        q = shlex.quote
        out = attachments._wsl_run(distro, f"sha256sum {q(final_wsl)}").decode()
        assert out.split()[0] == SHA
        _note(f"leg A: wsl-native write OK — sha256 verified in-distro for {EDGE_NAME!r}")

        # 2) The agent rendering is the NATIVE path (never /mnt for this store).
        agent_path = attachments.render_wsl_path(wsl_project["cwd"], rec)
        assert agent_path == final_wsl
        _note(f"leg A: agent rendering = native path {agent_path!r}")

        # 3) wslpath -w edge cases: spaces + unicode + the installed distro
        #    name — the materialized Windows path must open and match bytes.
        win = attachments._wsl_run(distro, f"wslpath -w {q(final_wsl)}").decode(
            "utf-8").strip()
        assert distro in win, f"distro name missing from wslpath -w output: {win!r}"
        got = Path(win).read_bytes()
        assert hashlib.sha256(got).hexdigest() == SHA
        _note(f"leg A: wslpath -w round-trip OK — {win!r} opens from Windows, bytes match")

        # 4) The sidecar meta landed beside the bytes (readable over UNC).
        meta_win = Path(win + ".meta.json")
        meta = json.loads(meta_win.read_text(encoding="utf-8"))
        assert meta["sha256"] == SHA and meta["citation"]["doc"] == "roadmap.md"
        _note("leg A: per-asset .meta.json sidecar readable over UNC, fields intact")

    def test_source_path_ingest_from_wsl_internal_file(self, wsl_project):
        distro, proj_wsl = wsl_project["distro"], wsl_project["proj_wsl"]
        import shlex
        q = shlex.quote
        src_wsl = f"{proj_wsl}/src örig file.bin"
        attachments._wsl_run(distro, f"cat > {q(src_wsl)}", input_bytes=PAYLOAD)
        src_unc = (rf"\\wsl.localhost\{distro}" + src_wsl.replace("/", "\\"))
        rec = attachments.ingest_source_path(wsl_project["cwd"], src_unc)
        assert rec["sha256"] == SHA
        assert rec["provenance"]["source"] == src_unc
        _note("leg A: source_path ingest from a WSL-internal file OK "
              f"(filename {rec['filename']!r})")

    def test_listing_reads_the_wsl_store(self, wsl_project):
        recs = attachments.list_assets(wsl_project["cwd"])
        names = {r["filename"] for r in recs}
        assert EDGE_NAME in names
        _note(f"leg A: list_assets over the WSL store OK — {sorted(names)!r}")


class TestAssetEndpointRenderLeg:
    """Leg B: the byte render through a real in-process app client."""

    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))
        with TestClient(main.app) as c:
            yield c

    @pytest.fixture()
    def proj(self, tmp_path):
        p = tmp_path / "proj"
        (p / ".git").mkdir(parents=True)
        return p

    def test_post_then_get_returns_exact_bytes_and_mime(self, client, proj):
        r = client.post("/library/assets", json={
            "cwd": str(proj), "filename": EDGE_NAME,
            "content_base64": base64.b64encode(PAYLOAD).decode(),
            "created_by": "live-test",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        url = body["http_url"]
        assert url.startswith("/assets/")
        g = client.get(url)
        assert g.status_code == 200
        assert g.content == PAYLOAD
        assert g.headers["content-type"].startswith("image/png")
        _note(f"leg B: TestClient POST->GET OK — {len(PAYLOAD)} bytes byte-identical, "
              f"content-type {g.headers['content-type']!r}, url {url!r}")

    def test_traversal_shapes_404(self, client, proj):
        r = client.post("/library/assets", json={
            "cwd": str(proj), "filename": "a.png",
            "content_base64": base64.b64encode(b"x").decode()})
        aid = r.json()["asset"]["id"]
        (proj / "secret.txt").write_text("s", encoding="utf-8")
        for path in (f"/assets/%2E%2E/secret.txt?cwd={proj}",
                     f"/assets/{aid}/a.png.meta.json?cwd={proj}",
                     f"/assets/{aid}/%2E%2E%5C%2E%2E%5Csecret.txt?cwd={proj}"):
            g = client.get(path)
            assert g.status_code == 404, f"{path} -> {g.status_code}"
        _note("leg B: traversal/meta-sidecar shapes all 404 through the real router")

    def test_agent_icons_route_keeps_precedence(self, client):
        icons = sorted((Path(__file__).parents[1] / "assets" / "icons" / "agents")
                       .glob("*.svg"))
        if not icons:
            pytest.skip("no agent icons shipped")
        g = client.get(f"/assets/agent-icons/{icons[0].stem}")
        assert g.status_code == 200
        assert g.headers["content-type"].startswith("image/svg")
        _note(f"leg B: /assets/agent-icons/{icons[0].stem} still routes to the "
              "icon endpoint (no shadowing by the asset route)")

    def test_uvicorn_spot_check_on_ephemeral_port(self, tmp_path, monkeypatch, proj):
        """Bonus: the same render through a REAL uvicorn socket (127.0.0.1:0)."""
        import uvicorn
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime2"))
        rec = attachments.ingest_bytes(str(proj), "sock.png", PAYLOAD)
        config = uvicorn.Config(main.app, host="127.0.0.1", port=0,
                                log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.time() + 20
            while not server.started:
                if time.time() > deadline:
                    pytest.fail("uvicorn did not start within 20s")
                time.sleep(0.1)
            port = server.servers[0].sockets[0].getsockname()[1]
            url = (f"http://127.0.0.1:{port}"
                   + attachments.render_http_url(str(proj), rec))
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "")
            assert data == PAYLOAD
            assert ctype.startswith("image/png")
            _note(f"leg B bonus: real uvicorn on 127.0.0.1:{port} served the bytes "
                  f"byte-identical (content-type {ctype!r})")
        finally:
            server.should_exit = True
            thread.join(timeout=10)
