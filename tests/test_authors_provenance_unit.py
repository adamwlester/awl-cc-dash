"""Hermetic unit tests for Authors-view provenance wiring (§8.5, §11 #41).

Decided contract (ARCHITECTURE §8.5, §11 #41; build plan
``dev/notes/2026-07-15-stage5-build-plan.md`` #41):

Provenance (created-by / when / session) is already stamped on a doc's paired
``.meta.json`` sidecar by ``library.set_provenance``. #41 is the SYSTEM-side
wiring that surfaces it onto the Library read path so the renderer's already-built
Authors lens can consume it — the listing (``list_markdown`` /
``GET /library/documents``) and the single-doc read (``read_document`` /
``GET /library/document``) both carry a ``provenance`` block. No renderer work.

What this file pins (pure file logic — no driver / WSL / network):
  * ``library.doc_provenance`` — reads the sidecar's provenance, ``{}`` when the
    sidecar is absent / un-stamped / corrupt (never raises).
  * ``list_markdown`` entries carry ``provenance`` (the stamped block for a doc
    with a sidecar, ``{}`` for one without), on top of the existing
    filename/path/size/modified keys (additive — nothing removed).
  * ``read_document`` carries ``provenance`` alongside content.

Everything runs on ``tmp_path`` — never a real project dir. No ``integration`` /
``slow`` mark.
"""

import sys
from pathlib import Path

# The sidecar runs with its own dir on sys.path (not the repo root).
SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import library  # noqa: E402


# ---------------------------------------------------------------------------
# doc_provenance — read the sidecar's provenance block, degrade to {}
# ---------------------------------------------------------------------------

class TestDocProvenance:
    def test_stamped_provenance_round_trips(self, tmp_path):
        md = tmp_path / "roadmap.md"
        md.write_text("# Roadmap", encoding="utf-8")
        library.set_provenance(md, created_by="coder-01", session="sess-1")
        prov = library.doc_provenance(md)
        assert prov["created_by"] == "coder-01"
        assert prov["session"] == "sess-1"
        # created_at is stamped on the first provenance write (§8.5).
        assert "created_at" in prov and "T" in prov["created_at"]

    def test_no_sidecar_is_empty(self, tmp_path):
        md = tmp_path / "plain.md"
        md.write_text("# Plain", encoding="utf-8")
        assert library.doc_provenance(md) == {}

    def test_sidecar_without_provenance_is_empty(self, tmp_path):
        # A sidecar that only carries a review (no provenance ever written).
        md = tmp_path / "reviewed.md"
        md.write_text("# Reviewed", encoding="utf-8")
        library.set_doc_review(md, verdict="approve", verdict_by="user")
        assert library.doc_provenance(md) == {}

    def test_corrupt_sidecar_degrades_to_empty(self, tmp_path):
        md = tmp_path / "broken.md"
        md.write_text("# Broken", encoding="utf-8")
        library.meta_path(md).write_text("{not json", encoding="utf-8")
        # load_meta degrades a corrupt sidecar to the skeleton -> {} provenance.
        assert library.doc_provenance(md) == {}


# ---------------------------------------------------------------------------
# list_markdown — provenance on every entry (additive to the existing shape)
# ---------------------------------------------------------------------------

class TestListingProvenance:
    def test_entry_carries_stamped_provenance(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Doc", encoding="utf-8")
        library.set_provenance(md, created_by="nova-3", session="s9")

        entries = library.list_markdown(str(tmp_path))
        assert len(entries) == 1
        e = entries[0]
        # The pre-existing keys are untouched (additive change)...
        assert e["filename"] == "doc.md"
        assert set(("filename", "path", "size", "modified")).issubset(e.keys())
        # ...and provenance now rides alongside.
        assert e["provenance"]["created_by"] == "nova-3"
        assert e["provenance"]["session"] == "s9"

    def test_entry_without_sidecar_has_empty_provenance(self, tmp_path):
        (tmp_path / "bare.md").write_text("# Bare", encoding="utf-8")
        e = library.list_markdown(str(tmp_path))[0]
        assert e["provenance"] == {}

    def test_mixed_listing_authors(self, tmp_path):
        a = tmp_path / "a.md"; a.write_text("a", encoding="utf-8")
        b = tmp_path / "b.md"; b.write_text("b", encoding="utf-8")
        library.set_provenance(a, created_by="alice")
        # b left un-stamped.
        by_name = {e["filename"]: e for e in library.list_markdown(str(tmp_path))}
        assert by_name["a.md"]["provenance"]["created_by"] == "alice"
        assert by_name["b.md"]["provenance"] == {}


# ---------------------------------------------------------------------------
# read_document — provenance alongside content
# ---------------------------------------------------------------------------

class TestReadDocumentProvenance:
    def test_read_carries_provenance(self, tmp_path):
        md = tmp_path / "spec.md"
        body = "# Spec\n\nbody"
        md.write_text(body, encoding="utf-8")
        library.set_provenance(md, created_by="rex-2", session="sX")

        doc = library.read_document(str(md))
        assert doc["content"] == body            # content unchanged
        assert doc["provenance"]["created_by"] == "rex-2"
        assert doc["provenance"]["session"] == "sX"

    def test_read_without_sidecar_has_empty_provenance(self, tmp_path):
        md = tmp_path / "no-meta.md"
        md.write_text("x", encoding="utf-8")
        assert library.read_document(str(md))["provenance"] == {}
