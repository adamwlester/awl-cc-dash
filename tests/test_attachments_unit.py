"""Hermetic unit tests for attachments (§10 #1 — Option A asset materialization).

Pure file logic on ``tmp_path`` stores — no WSL2/tmux, no live agent, no HTTP
server (endpoint functions are called directly via ``asyncio.run``). Proves the
decided §10 #1 build-ladder behavior (research: Option A in
``dev/notes/research/attachment-citation-path-materialization-report.md``):

  * **Ingest (leg a)** — ``ingest_bytes`` / ``ingest_source_path`` copy
    attachment bytes into ``<project>/.awl-cc-dash/assets/<asset_id>/<name>``
    with a per-asset ``<name>.meta.json`` sidecar beside the bytes (the §8.5
    pairing convention adapted to full-filename pairing) holding
    ``schema_version: 1`` · sha256 · size · mime · created · provenance
    (who/when/source/session) · the optional §7.14 **citation anchor**
    (doc + location). Writes are atomic (tmp + rename, no residue) and
    hash-verified. The canonical record is project-relative (``rel_path``) —
    never a receiver-specific absolute path. Both upload forms land the same
    store shape: raw bytes (the endpoint's base64-JSON body) and a local
    source-path reference in any spelling the storage layer folds (``C:\\…``,
    ``/mnt/c/…``), the original spelling kept as ``provenance.source``.
  * **Filename safety** — separators/``..``/empty refused; Windows-forbidden
    chars sanitized to ``_`` (the name must stay addressable from BOTH sides
    of the WSL boundary); Windows reserved device names (``NUL``, ``COM1``…,
    bare or extension-suffixed) prefixed ``_`` (bare ``NUL`` broke
    ``os.replace`` outright); spaces/unicode/case preserved; the
    ``.meta.json`` suffix reserved; over-long names truncated keeping the
    extension. The ``AWL_ASSET_MAX_MB`` cap fires on ``stat()`` BEFORE
    ``read_bytes`` on the source-path leg — an over-cap file never buffers.
  * **Write-leg selection** — ``store_kind`` picks the leg automatically from
    the canonical project root: ``("windows", None)`` for drive-letter roots
    (plain atomic I/O — the common case), ``("wsl", <distro>)`` for
    ``\\\\wsl.localhost\\<distro>\\…`` / ``\\\\wsl$\\…`` roots (the WSL-native
    ``cat > tmp && mv`` path — live-proven in ``test_attachments_live.py``).
  * **Serve resolution (leg b)** — ``asset_file_path`` is the traversal gate
    for ``GET /assets/{id}/{filename}``: plain-segment-only, sidecars not
    addressable (case-INSENSITIVELY — NTFS would resolve a case-tricked
    ``.META.JSON``), and the resolved file must live strictly inside the
    store's ``assets/`` dir — anything else resolves ``None`` (the endpoint
    404s).
  * **Per-receiver rendering (leg d)** — absolute paths are *renderings*,
    never stored state: the agent gets the WSL-readable absolute path
    (``/mnt/<drive>/…`` for Windows stores, native ``/home/…`` for
    WSL-internal stores — via the proven ``storage.doc_path_wsl``, which
    strips BOTH the ``\\\\wsl.localhost\\`` and legacy ``\\\\wsl$\\`` UNC
    spellings), the renderer gets the quoted HTTP URL
    (``/assets/{id}/{name}?cwd=…``).
  * **The message-attachments block** — lead line (prompt-library-resolved,
    group ``attachments``/item ``lead``, shipped default verbatim ==
    ``ATTACHMENTS_LEAD``, project copy overrides) + one ``- <path>`` bullet
    per asset, citation anchors inline (``(cites <doc> @ <location>)``).
  * **The send-flow wiring (§7.3/§7.14)** — ``POST /sessions/{id}/send`` with
    ``attachments: [asset ids]`` appends the ONE attributed block to the
    delivered text on every disposition (inject rides it too); unknown ids and
    a cwd-less agent are honest 400s, never silent drops.
  * **The endpoints** — ``POST /library/assets`` (exactly one byte source;
    base64 validated; citation validated; honest 400/404 degrades),
    ``GET /library/assets`` (id · filename · mime · size · created ·
    provenance + renderings; loose ``assets/``-root files list with
    ``id: null``), and ``GET /assets/{id}/{filename}`` (FileResponse with the
    stored mime; traversal → 404).
  * **The §7.16 recursive-listing debt** — ``GET /library/documents`` with
    ``subdir=plans|docs`` walks nested store trees (and the legacy
    ``<root>/<subdir>`` fallback) recursively with ``rel_path`` entries, while
    the no-subdir root browse stays top-level and the store's
    ``docs/prompts/`` subtree (the §11 #45 prompt-library project copy —
    ``/prompt-library``'s data, not documents) never lists (see also
    ``test_library_unit.TestListMarkdown`` — incl. the junction-cycle safety
    proof).

Everything operates on ``tmp_path`` — never a real project dir. Project dirs
get a ``.git`` marker so ``storage.project_root`` pins to the tmp dir. These
carry neither the ``integration`` nor the ``slow`` mark.
"""

import sys
from pathlib import Path

# The sidecar runs with its own dir on sys.path (not the repo root).
_SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import asyncio  # noqa: E402
import base64  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

import attachments  # noqa: E402
import eventbus  # noqa: E402
import library  # noqa: E402
import main  # noqa: E402
import prompt_library  # noqa: E402
import storage  # noqa: E402
from bridge.paths import win_to_wsl  # noqa: E402  (conftest puts the repo root on sys.path)

# Binary payload with NULs + high bytes — asserts byte fidelity, not text luck.
PAYLOAD = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) + b"\x00" * 32


def _proj(tmp_path: Path) -> Path:
    """A throwaway project dir whose canonical root pins to itself."""
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    return proj


def _ingest(proj: Path, name: str = "photo.png", data: bytes = PAYLOAD, **kw) -> dict:
    return attachments.ingest_bytes(str(proj), name, data, **kw)


# ---------------------------------------------------------------------------
# Filename safety
# ---------------------------------------------------------------------------

class TestSafeAssetFilename:
    def test_preserves_spaces_unicode_case(self):
        assert attachments.safe_asset_filename("Mein Märchen ✓.PNG") == \
            "Mein Märchen ✓.PNG"

    def test_rejects_separators(self):
        for bad in ("a/b.png", "a\\b.png"):
            with pytest.raises(ValueError):
                attachments.safe_asset_filename(bad)

    def test_rejects_dotdot_and_empty(self):
        with pytest.raises(ValueError):
            attachments.safe_asset_filename("a..b.png")
        with pytest.raises(ValueError):
            attachments.safe_asset_filename("   ")

    def test_windows_forbidden_chars_sanitize(self):
        # <>:"|?* and control chars become _ so the name stays addressable
        # from both sides of the WSL boundary.
        assert attachments.safe_asset_filename('we:ird?"n*ame.png') == \
            "we_ird__n_ame.png"

    def test_trailing_dots_and_spaces_stripped(self):
        assert attachments.safe_asset_filename("name.png. . ") == "name.png"

    def test_leading_dot_prefixed(self):
        # Hidden/tmp-style names collide with internal sidecar/tmp naming.
        assert attachments.safe_asset_filename(".env") == "_env"

    def test_meta_suffix_reserved(self):
        with pytest.raises(ValueError):
            attachments.safe_asset_filename("sneaky.meta.json")

    def test_overlong_truncates_keeping_extension(self):
        name = attachments.safe_asset_filename("x" * 400 + ".png")
        assert len(name) <= 150 and name.endswith(".png")

    def test_reserved_device_names_prefixed(self):
        # Bare `NUL` breaks os.replace outright on a Windows store
        # (FileExistsError — probe-proven on this build), and the classic
        # rule also reserves the stem before an extension — sanitize both.
        for bad, safe in (("NUL", "_NUL"), ("nul.txt", "_nul.txt"),
                          ("CON", "_CON"), ("COM1.bin", "_COM1.bin"),
                          ("lpt9.png", "_lpt9.png"), ("AUX.tar.gz", "_AUX.tar.gz")):
            assert attachments.safe_asset_filename(bad) == safe
        # Names that merely START with a reserved word are untouched.
        assert attachments.safe_asset_filename("CONFIG.md") == "CONFIG.md"
        assert attachments.safe_asset_filename("nullable.png") == "nullable.png"

    def test_reserved_name_ingest_lands_sanitized_not_500(self, tmp_path):
        # Regression: ingesting filename 'NUL' used to escape as an unmapped
        # FileExistsError (raw 500). It now lands as '_NUL', honestly renamed.
        proj = _proj(tmp_path)
        rec = _ingest(proj, name="NUL")
        assert rec["filename"] == "_NUL"
        assert (proj / ".awl-cc-dash" / "assets" / rec["id"] / "_NUL").is_file()


# ---------------------------------------------------------------------------
# Write-leg selection
# ---------------------------------------------------------------------------

class TestStoreKind:
    def test_windows_drive_root(self, tmp_path):
        proj = _proj(tmp_path)
        assert attachments.store_kind(str(proj)) == ("windows", None)

    def test_wsl_localhost_root(self, monkeypatch):
        monkeypatch.setattr(
            attachments.storage, "project_root",
            lambda cwd: Path(r"\\wsl.localhost\Ubuntu-24.04\home\u\proj"))
        assert attachments.store_kind("x") == ("wsl", "Ubuntu-24.04")

    def test_wsl_dollar_root(self, monkeypatch):
        monkeypatch.setattr(
            attachments.storage, "project_root",
            lambda cwd: Path(r"\\wsl$\Ubuntu\home\u\proj"))
        assert attachments.store_kind("x") == ("wsl", "Ubuntu")

    def test_no_cwd_raises(self):
        with pytest.raises(ValueError):
            attachments.store_kind(None)


# ---------------------------------------------------------------------------
# Ingest — the Windows (plain atomic I/O) leg on tmp stores
# ---------------------------------------------------------------------------

class TestIngestBytes:
    def test_bytes_land_in_store_layout(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        final = proj / ".awl-cc-dash" / "assets" / rec["id"] / "photo.png"
        assert final.read_bytes() == PAYLOAD
        assert rec["rel_path"] == f"assets/{rec['id']}/photo.png"

    def test_meta_sidecar_beside_bytes_matches_record(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, created_by="op", session="s9")
        meta = proj / ".awl-cc-dash" / "assets" / rec["id"] / "photo.png.meta.json"
        assert json.loads(meta.read_text(encoding="utf-8")) == rec

    def test_record_shape(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, created_by="op", session="s9")
        assert rec["schema_version"] == 1
        assert rec["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
        assert rec["size"] == len(PAYLOAD)
        assert rec["mime"] == "image/png"
        assert "T" in rec["created"]
        prov = rec["provenance"]
        assert prov["created_by"] == "op" and prov["session"] == "s9"
        assert prov["source"] == "upload" and prov["created_at"] == rec["created"]
        assert rec["citation"] is None

    def test_atomic_no_tmp_residue(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        asset_dir = proj / ".awl-cc-dash" / "assets" / rec["id"]
        assert not [p for p in asset_dir.iterdir() if ".tmp" in p.name]

    def test_unique_ids_for_same_name(self, tmp_path):
        proj = _proj(tmp_path)
        a, b = _ingest(proj), _ingest(proj)
        assert a["id"] != b["id"]  # immutable assets — never overwritten

    def test_filename_sanitized_on_ingest(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, name="we:ird?.png")
        assert rec["filename"] == "we_ird_.png"
        assert (proj / ".awl-cc-dash" / "assets" / rec["id"] / "we_ird_.png").is_file()

    def test_citation_anchor_persists(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, citation={"doc": "roadmap.md", "location": "§2 Goals"})
        assert rec["citation"] == {"doc": "roadmap.md", "location": "§2 Goals"}
        meta = proj / ".awl-cc-dash" / "assets" / rec["id"] / "photo.png.meta.json"
        assert json.loads(meta.read_text(encoding="utf-8"))["citation"] == rec["citation"]

    def test_citation_requires_doc(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(ValueError):
            _ingest(proj, citation={"location": "§2"})

    def test_size_cap_honored(self, tmp_path, monkeypatch):
        proj = _proj(tmp_path)
        monkeypatch.setenv("AWL_ASSET_MAX_MB", "1")
        with pytest.raises(ValueError):
            _ingest(proj, data=b"x" * (1024 * 1024 + 1))

    def test_no_cwd_raises(self):
        with pytest.raises(ValueError):
            attachments.ingest_bytes(None, "a.png", b"x")


class TestIngestSourcePath:
    def test_copies_from_windows_path(self, tmp_path):
        proj = _proj(tmp_path)
        src = tmp_path / "original photo.png"
        src.write_bytes(PAYLOAD)
        rec = attachments.ingest_source_path(str(proj), str(src))
        assert rec["filename"] == "original photo.png"
        assert rec["provenance"]["source"] == str(src)
        final = proj / ".awl-cc-dash" / "assets" / rec["id"] / rec["filename"]
        assert final.read_bytes() == PAYLOAD

    def test_accepts_mnt_alias_spelling(self, tmp_path):
        # The /mnt/<drive> WSL alias of a Windows source folds back through
        # storage.normalize_path_alias — same bytes, original spelling audited.
        proj = _proj(tmp_path)
        src = tmp_path / "alias.bin"
        src.write_bytes(PAYLOAD)
        alias = win_to_wsl(str(src))
        assert alias.startswith("/mnt/")
        rec = attachments.ingest_source_path(str(proj), alias)
        assert rec["provenance"]["source"] == alias
        assert rec["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()

    def test_missing_source_raises_filenotfound(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(FileNotFoundError):
            attachments.ingest_source_path(str(proj), str(tmp_path / "nope.bin"))

    def test_directory_source_raises_valueerror(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(ValueError):
            attachments.ingest_source_path(str(proj), str(tmp_path))

    def test_explicit_filename_overrides_basename(self, tmp_path):
        proj = _proj(tmp_path)
        src = tmp_path / "raw.bin"
        src.write_bytes(b"x")
        rec = attachments.ingest_source_path(str(proj), str(src), "renamed.bin")
        assert rec["filename"] == "renamed.bin"

    def test_size_cap_enforced_before_the_read(self, tmp_path, monkeypatch):
        # Regression: the AWL_ASSET_MAX_MB cap exists because bytes are held
        # in memory through hash + write — so an over-cap source_path must be
        # refused on stat(), BEFORE read_bytes buffers it (a 20 GB mis-attach
        # must never allocate 20 GB just to be told no).
        proj = _proj(tmp_path)
        src = tmp_path / "huge.bin"
        src.write_bytes(b"x" * (1024 * 1024 + 1))
        monkeypatch.setenv("AWL_ASSET_MAX_MB", "1")

        def _no_read(self):
            raise AssertionError("read_bytes must not run for an over-cap source")

        monkeypatch.setattr(Path, "read_bytes", _no_read)
        with pytest.raises(ValueError, match="ingest limit"):
            attachments.ingest_source_path(str(proj), str(src))


# ---------------------------------------------------------------------------
# Serve resolution — the traversal gate
# ---------------------------------------------------------------------------

class TestAssetFilePath:
    def test_resolves_ingested_asset(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        p = attachments.asset_file_path(str(proj), rec["id"], rec["filename"])
        assert p is not None and p.read_bytes() == PAYLOAD

    def test_refuses_traversal_segments(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        (proj / "secret.txt").write_text("s", encoding="utf-8")
        for aid, name in (("..", "secret.txt"),
                          (rec["id"], "../../../secret.txt"),
                          (rec["id"], "..\\..\\secret.txt"),
                          ("a/b", "x.png"), ("", "x.png"), (rec["id"], "")):
            assert attachments.asset_file_path(str(proj), aid, name) is None

    def test_meta_sidecar_not_addressable(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        assert attachments.asset_file_path(
            str(proj), rec["id"], rec["filename"] + ".meta.json") is None

    def test_meta_sidecar_not_addressable_case_tricked(self, tmp_path):
        # Regression: NTFS is case-insensitive, so `photo.png.META.JSON`
        # resolved the real sidecar — the gate must refuse the suffix
        # case-insensitively (matching ingest's reservation, and matching
        # what a case-sensitive ext4 WSL store does anyway).
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        for tricked in (".META.JSON", ".Meta.Json", ".meta.JSON"):
            assert attachments.asset_file_path(
                str(proj), rec["id"], rec["filename"] + tricked) is None

    def test_unknown_id_or_name_is_none(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        assert attachments.asset_file_path(str(proj), "beefbeefbeef", "photo.png") is None
        assert attachments.asset_file_path(str(proj), rec["id"], "other.png") is None


# ---------------------------------------------------------------------------
# Per-receiver rendering — paths are renderings, never stored state
# ---------------------------------------------------------------------------

class TestRenderings:
    def test_agent_path_windows_store_is_mnt_form(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, name="a b.png")
        got = attachments.render_wsl_path(str(proj), rec)
        expected = win_to_wsl(
            str(proj / ".awl-cc-dash" / "assets" / rec["id"] / "a b.png"))
        assert got == expected and got.startswith("/mnt/")

    def test_agent_path_wsl_store_is_native_form(self, monkeypatch):
        # A WSL-internal store's UNC assets dir renders to the NATIVE /home/…
        # path (the doc_path_wsl UNC strip) — never a /mnt mistake.
        monkeypatch.setattr(
            attachments.storage, "assets_dir",
            lambda cwd: Path(r"\\wsl.localhost\Ubuntu\home\u\proj\.awl-cc-dash\assets"))
        rec = {"id": "abc123", "filename": "a b.png"}
        assert attachments.render_wsl_path("x", rec) == \
            "/home/u/proj/.awl-cc-dash/assets/abc123/a b.png"

    def test_agent_path_wsl_dollar_store_also_native(self, monkeypatch):
        # Regression: the legacy \\wsl$\ spelling used to render an unopenable
        # //wsl$/… string (doc_path_wsl only stripped wsl.localhost) — a
        # silent wrong-path delivery to the agent. Both UNC spellings now
        # strip to the same native path.
        monkeypatch.setattr(
            attachments.storage, "assets_dir",
            lambda cwd: Path(r"\\wsl$\Ubuntu\home\u\proj\.awl-cc-dash\assets"))
        rec = {"id": "abc123", "filename": "a b.png"}
        assert attachments.render_wsl_path("x", rec) == \
            "/home/u/proj/.awl-cc-dash/assets/abc123/a b.png"

    def test_http_url_quotes_filename_and_cwd(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, name="a b.png")
        url = attachments.render_http_url(str(proj), rec)
        assert url.startswith(f"/assets/{rec['id']}/a%20b.png?cwd=")
        assert " " not in url

    def test_http_url_none_for_loose_media(self, tmp_path):
        proj = _proj(tmp_path)
        assert attachments.render_http_url(str(proj), {"id": None, "filename": "x.png"}) is None


# ---------------------------------------------------------------------------
# The message-attachments block (§7.14)
# ---------------------------------------------------------------------------

class TestAttachmentsBlock:
    def test_lead_plus_bullets(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        block = attachments.attachments_block(str(proj), [rec])
        lines = block.splitlines()
        assert lines[0] == attachments.ATTACHMENTS_LEAD
        assert lines[1] == f"- {attachments.render_wsl_path(str(proj), rec)}"

    def test_citation_rides_inline(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, citation={"doc": "roadmap.md", "location": "§2"})
        block = attachments.attachments_block(str(proj), [rec])
        assert block.splitlines()[1].endswith("(cites roadmap.md @ §2)")

    def test_empty_records_render_nothing(self, tmp_path):
        proj = _proj(tmp_path)
        assert attachments.attachments_block(str(proj), []) == ""
        assert attachments.attachments_block(str(proj), None) == ""

    def test_shipped_default_seed_matches_constant_verbatim(self):
        # §11 #45: the assets/prompts/actions.md seed carries the in-code
        # fallback VERBATIM (behavior-preserving), like attached-docs/lead.
        assert prompt_library.resolve("attachments", "lead") == \
            attachments.ATTACHMENTS_LEAD

    def test_project_copy_overrides_lead(self, tmp_path):
        proj = _proj(tmp_path)
        prompts = storage.ensure_docs_dir(str(proj)) / "prompts"
        prompts.mkdir(parents=True, exist_ok=True)
        (prompts / "actions.md").write_text(
            "## attachments\n\n### lead\n\nPROJECT ATTACH LEAD:\n",
            encoding="utf-8")
        rec = _ingest(proj)
        block = attachments.attachments_block(str(proj), [rec])
        assert block.startswith("PROJECT ATTACH LEAD:")
        assert attachments.ATTACHMENTS_LEAD not in block


# ---------------------------------------------------------------------------
# Listing — GET /library/assets data
# ---------------------------------------------------------------------------

class TestListAssets:
    def test_lists_ingested_assets_sorted(self, tmp_path):
        proj = _proj(tmp_path)
        a = _ingest(proj, name="b.png")
        b = _ingest(proj, name="a.png")
        recs = attachments.list_assets(str(proj))
        assert {r["id"] for r in recs} == {a["id"], b["id"]}
        assert [r["rel_path"] for r in recs] == sorted(r["rel_path"] for r in recs)

    def test_missing_assets_dir_is_empty(self, tmp_path):
        proj = _proj(tmp_path)
        assert attachments.list_assets(str(proj)) == []

    def test_loose_files_list_with_null_id(self, tmp_path):
        proj = _proj(tmp_path)
        _ingest(proj)
        loose = proj / ".awl-cc-dash" / "assets" / "dropped.gif"
        loose.write_bytes(b"GIF89a")
        recs = attachments.list_assets(str(proj))
        by_name = {r["filename"]: r for r in recs}
        assert by_name["dropped.gif"]["id"] is None
        assert by_name["dropped.gif"]["mime"] == "image/gif"
        assert by_name["dropped.gif"]["provenance"] == {}

    def test_metaless_asset_dir_synthesizes_record(self, tmp_path):
        proj = _proj(tmp_path)
        d = proj / ".awl-cc-dash" / "assets" / "handmade01"
        d.mkdir(parents=True)
        (d / "pic.jpg").write_bytes(b"\xff\xd8\xff")
        rec = attachments.load_asset_record(str(proj), "handmade01")
        assert rec["id"] == "handmade01" and rec["filename"] == "pic.jpg"
        assert rec["mime"] == "image/jpeg" and rec["sha256"] is None


# ---------------------------------------------------------------------------
# Endpoints — direct-call (no HTTP server; byte render is live-proven)
# ---------------------------------------------------------------------------

class TestAssetEndpoints:
    def _post(self, **kw):
        return asyncio.run(main.library_ingest_asset(main.AssetIngestRequest(**kw)))

    def test_ingest_base64_upload(self, tmp_path):
        proj = _proj(tmp_path)
        out = self._post(cwd=str(proj), filename="photo.png",
                         content_base64=base64.b64encode(PAYLOAD).decode())
        rec = out["asset"]
        assert (proj / ".awl-cc-dash" / "assets" / rec["id"] / "photo.png"
                ).read_bytes() == PAYLOAD
        assert out["agent_path"].startswith("/mnt/")
        assert out["http_url"].startswith(f"/assets/{rec['id']}/photo.png?cwd=")

    def test_ingest_source_path(self, tmp_path):
        proj = _proj(tmp_path)
        src = tmp_path / "src.bin"
        src.write_bytes(PAYLOAD)
        out = self._post(cwd=str(proj), source_path=str(src))
        assert out["asset"]["provenance"]["source"] == str(src)

    def test_exactly_one_byte_source(self, tmp_path):
        proj = _proj(tmp_path)
        for kw in (dict(), dict(content_base64="eA==", source_path="C:/x")):
            with pytest.raises(HTTPException) as e:
                self._post(cwd=str(proj), filename="a.png", **kw)
            assert e.value.status_code == 400

    def test_bad_base64_is_400(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(HTTPException) as e:
            self._post(cwd=str(proj), filename="a.png", content_base64="@@not-b64@@")
        assert e.value.status_code == 400

    def test_base64_requires_filename(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(HTTPException) as e:
            self._post(cwd=str(proj), content_base64="eA==")
        assert e.value.status_code == 400

    def test_missing_source_is_404(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(HTTPException) as e:
            self._post(cwd=str(proj), source_path=str(tmp_path / "nope.bin"))
        assert e.value.status_code == 404

    def test_no_cwd_is_400(self):
        with pytest.raises(HTTPException) as e:
            self._post(cwd="", filename="a.png", content_base64="eA==")
        assert e.value.status_code == 400

    def test_listing_endpoint_carries_renderings(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        rows = asyncio.run(main.library_list_assets(cwd=str(proj)))
        assert rows[0]["id"] == rec["id"]
        assert rows[0]["agent_path"].startswith("/mnt/")
        assert rows[0]["http_url"].startswith(f"/assets/{rec['id']}/")
        for key in ("filename", "mime", "size", "created", "provenance"):
            assert key in rows[0]

    def test_serve_returns_fileresponse_with_stored_mime(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        resp = asyncio.run(main.serve_asset(rec["id"], rec["filename"], str(proj)))
        assert Path(resp.path).read_bytes() == PAYLOAD
        assert resp.media_type == "image/png"

    def test_serve_traversal_is_404(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        (proj / "secret.txt").write_text("s", encoding="utf-8")
        for aid, name in (("..", "secret.txt"),
                          (rec["id"], "../../secret.txt"),
                          (rec["id"], "photo.png.meta.json"),
                          (rec["id"], "photo.png.META.JSON"),  # NTFS case trick
                          ("nosuchid", "photo.png")):
            with pytest.raises(HTTPException) as e:
                asyncio.run(main.serve_asset(aid, name, str(proj)))
            assert e.value.status_code == 404


# ---------------------------------------------------------------------------
# Send-flow wiring — attachments ride the delivered text (§7.3/§7.14)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_event_bus():
    # The cross-agent bus is process-global (like `sessions`) — reset per test.
    eventbus.reset()
    yield
    eventbus.reset()


class _FakeDriver:
    name = "fake"

    def __init__(self):
        self.sent = []
        self.interrupted = 0

    def supports(self, _cap):
        return False

    async def send(self, prompt):
        self.sent.append(prompt)

    async def interrupt(self):
        self.interrupted += 1


def _session(cwd: str | None):
    s = main.SessionState(
        session_id="s1", agent_type=None, model=None,
        permission_mode="default", cwd=cwd, system_prompt=None,
        driver_name="bridge",
    )
    s.driver = _FakeDriver()
    s.status = "idle"
    return s


class TestSendFlowAttachments:
    def _with_session(self, cwd):
        s = _session(cwd)
        main.sessions["s1"] = s
        return s

    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_delivered_text_appends_the_attributed_block(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        s = self._with_session(str(proj))
        asyncio.run(main.send_prompt("s1", main.SendPromptRequest(
            prompt="look at this", attachments=[rec["id"]])))
        assert len(s.driver.sent) == 1
        delivered = s.driver.sent[0]
        block = attachments.attachments_block(str(proj), [rec])
        assert delivered == f"look at this\n\n{block}"
        assert attachments.render_wsl_path(str(proj), rec) in delivered

    def test_citation_anchor_rides_the_delivery(self, tmp_path):
        proj = _proj(tmp_path)
        rec = _ingest(proj, citation={"doc": "roadmap.md", "location": "§2"})
        s = self._with_session(str(proj))
        asyncio.run(main.send_prompt("s1", main.SendPromptRequest(
            prompt="see the citation", attachments=[rec["id"]])))
        assert "(cites roadmap.md @ §2)" in s.driver.sent[0]

    def test_unknown_asset_id_is_400_never_a_silent_drop(self, tmp_path):
        proj = _proj(tmp_path)
        s = self._with_session(str(proj))
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.send_prompt("s1", main.SendPromptRequest(
                prompt="x", attachments=["nosuchasset"])))
        assert e.value.status_code == 400
        assert s.driver.sent == []  # nothing was delivered

    def test_attachments_without_cwd_is_400(self):
        self._with_session(None)
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.send_prompt("s1", main.SendPromptRequest(
                prompt="x", attachments=["abc123"])))
        assert e.value.status_code == 400

    def test_inject_disposition_carries_the_block(self, tmp_path, monkeypatch):
        proj = _proj(tmp_path)
        rec = _ingest(proj)
        self._with_session(str(proj))
        captured = {}

        def _fake_enqueue(agent, text, kind="inject", source="user"):
            captured["text"] = text
            return {"id": "inj1"}

        monkeypatch.setattr(main.hookbus, "enqueue_inject", _fake_enqueue)
        r = asyncio.run(main.send_prompt("s1", main.SendPromptRequest(
            prompt="mid-run context", disposition="inject",
            attachments=[rec["id"]])))
        assert r["status"] == "injected"
        assert attachments.render_wsl_path(str(proj), rec) in captured["text"]

    def test_send_without_attachments_is_byte_for_byte_unchanged(self, tmp_path):
        proj = _proj(tmp_path)
        s = self._with_session(str(proj))
        asyncio.run(main.send_prompt("s1", main.SendPromptRequest(prompt="plain")))
        assert s.driver.sent == ["plain"]


# ---------------------------------------------------------------------------
# §7.16 debt — recursive store listing through the endpoint
# ---------------------------------------------------------------------------

class TestRecursiveDocumentListing:
    def test_store_plans_walks_nested_trees(self, tmp_path):
        proj = _proj(tmp_path)
        plans = storage.ensure_plans_dir(str(proj))
        (plans / "top.md").write_text("x", encoding="utf-8")
        nested = plans / "phase-1"
        nested.mkdir()
        (nested / "plan.md").write_text("x", encoding="utf-8")
        entries = asyncio.run(main.library_documents(cwd=str(proj), subdir="plans"))
        rels = [e["rel_path"] for e in entries]
        assert rels == ["phase-1/plan.md", "top.md"]

    def test_legacy_fallback_also_walks(self, tmp_path):
        proj = _proj(tmp_path)
        legacy = proj / "docs" / "guides"
        legacy.mkdir(parents=True)
        (legacy / "howto.md").write_text("x", encoding="utf-8")
        entries = asyncio.run(main.library_documents(cwd=str(proj), subdir="docs"))
        assert [e["rel_path"] for e in entries] == ["guides/howto.md"]

    def test_root_browse_stays_top_level(self, tmp_path):
        proj = _proj(tmp_path)
        (proj / "readme.md").write_text("x", encoding="utf-8")
        sub = proj / "deep"
        sub.mkdir()
        (sub / "nested.md").write_text("x", encoding="utf-8")
        names = {e["filename"]
                 for e in asyncio.run(main.library_documents(cwd=str(proj)))}
        assert names == {"readme.md"}

    def test_docs_listing_excludes_the_prompt_library_copy(self, tmp_path):
        # Regression: the recursive docs walk leaked <store>/docs/prompts/
        # (the §11 #45 prompt-library project copy) into the Documents surface
        # as ordinary deletable/commentable docs. It is /prompt-library data —
        # the listing must not offer it.
        proj = _proj(tmp_path)
        docs = storage.ensure_docs_dir(str(proj))
        (docs / "teamdoc.md").write_text("x", encoding="utf-8")
        prompts = docs / "prompts"
        prompts.mkdir()
        (prompts / "actions.md").write_text("## g\n\n### i\n\nX\n", encoding="utf-8")
        entries = asyncio.run(main.library_documents(cwd=str(proj), subdir="docs"))
        assert [e["rel_path"] for e in entries] == ["teamdoc.md"]
