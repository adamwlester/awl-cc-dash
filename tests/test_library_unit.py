"""Hermetic unit tests for the Library module (v1 = read + render).

Pure file logic — no driver, no WSL2/tmux, no live agent, no servers. Proves:

  * ``list_markdown`` enumerates ``.md`` files under a directory (optionally a
    ``plans`` subdir), with size + modified, skipping non-``.md`` and missing dirs.
  * ``read_document`` returns ``{filename, path, content}`` and raises on absent.
  * The plan-review side-store (a JSON object keyed by plan FILENAME, carrying the
    plan↔agent owner mapping) round-trips through a real JSON file under a tmp
    ``.awl/`` dir — set→get, partial-update merges fields, owner mapping persists,
    remove works, and ``load`` on a missing file is ``{}``.

Everything operates on ``tmp_path`` — never a real project dir. These carry
neither the ``integration`` nor the ``slow`` mark.
"""

import sys
from pathlib import Path

# The sidecar runs with its own dir on sys.path (not the repo root).
SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import json  # noqa: E402

import pytest  # noqa: E402

import library  # noqa: E402


# ---------------------------------------------------------------------------
# list_markdown — enumerate .md docs/plans under a directory
# ---------------------------------------------------------------------------

class TestListMarkdown:
    def test_finds_md_and_skips_non_md(self, tmp_path):
        (tmp_path / "alpha.md").write_text("# Alpha", encoding="utf-8")
        (tmp_path / "beta.md").write_text("# Beta", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("plain", encoding="utf-8")
        (tmp_path / "README").write_text("no ext", encoding="utf-8")

        entries = library.list_markdown(str(tmp_path))
        names = {e["filename"] for e in entries}
        assert names == {"alpha.md", "beta.md"}

    def test_entry_shape_has_size_path_modified(self, tmp_path):
        body = "# Title\n\nbody text here"
        f = tmp_path / "doc.md"
        f.write_text(body, encoding="utf-8")

        entries = library.list_markdown(str(tmp_path))
        assert len(entries) == 1
        e = entries[0]
        assert e["filename"] == "doc.md"
        assert Path(e["path"]) == f
        # size is the file's byte length on disk.
        assert e["size"] == f.stat().st_size
        # modified is an ISO-8601 string.
        assert isinstance(e["modified"], str) and "T" in e["modified"]

    def test_subdir_scopes_to_plans(self, tmp_path):
        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "phase-1.md").write_text("plan", encoding="utf-8")
        # A top-level .md must NOT show up when we scope to the plans subdir.
        (tmp_path / "toplevel.md").write_text("doc", encoding="utf-8")

        entries = library.list_markdown(str(tmp_path), subdir="plans")
        names = {e["filename"] for e in entries}
        assert names == {"phase-1.md"}

    def test_missing_dir_returns_empty(self, tmp_path):
        assert library.list_markdown(str(tmp_path / "nope")) == []

    def test_missing_subdir_returns_empty(self, tmp_path):
        assert library.list_markdown(str(tmp_path), subdir="plans") == []

    def test_a_file_path_as_root_returns_empty(self, tmp_path):
        f = tmp_path / "a.md"
        f.write_text("x", encoding="utf-8")
        # Pointed at a file, not a dir -> nothing to list.
        assert library.list_markdown(str(f)) == []

    def test_skips_subdirectories_named_like_md(self, tmp_path):
        # A directory whose name ends in .md is not a markdown document.
        (tmp_path / "weird.md").mkdir()
        (tmp_path / "real.md").write_text("x", encoding="utf-8")
        names = {e["filename"] for e in library.list_markdown(str(tmp_path))}
        assert names == {"real.md"}

    def test_sorted_by_filename(self, tmp_path):
        for n in ("c.md", "a.md", "b.md"):
            (tmp_path / n).write_text("x", encoding="utf-8")
        names = [e["filename"] for e in library.list_markdown(str(tmp_path))]
        assert names == ["a.md", "b.md", "c.md"]


# ---------------------------------------------------------------------------
# read_document — render a single doc's content
# ---------------------------------------------------------------------------

class TestReadDocument:
    def test_returns_content(self, tmp_path):
        body = "# Heading\n\nSome **markdown** body.\n"
        f = tmp_path / "doc.md"
        f.write_text(body, encoding="utf-8")

        doc = library.read_document(str(f))
        assert doc["filename"] == "doc.md"
        assert Path(doc["path"]) == f
        assert doc["content"] == body

    def test_unicode_content_round_trips(self, tmp_path):
        body = "# Café — résumé\n\nem—dash and ✓ check\n"
        f = tmp_path / "u.md"
        f.write_text(body, encoding="utf-8")
        assert library.read_document(str(f))["content"] == body

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            library.read_document(str(tmp_path / "ghost.md"))


# ---------------------------------------------------------------------------
# Plan-review side-store — JSON keyed by plan FILENAME (owner/state/verdict/...)
# ---------------------------------------------------------------------------

class TestReviewStore:
    def _review_path(self, tmp_path):
        # Mirror the real layout: <project>/.awl/plan-reviews.json. The .awl dir
        # does NOT exist yet — set_review must create it.
        return tmp_path / "proj" / ".awl" / "plan-reviews.json"

    def test_load_missing_file_is_empty(self, tmp_path):
        assert library.load_reviews(str(self._review_path(tmp_path))) == {}

    def test_get_missing_is_none(self, tmp_path):
        rp = self._review_path(tmp_path)
        assert library.get_review(str(rp), "phase-1.md") is None

    def test_set_creates_file_and_parent_dir(self, tmp_path):
        rp = self._review_path(tmp_path)
        assert not rp.exists()
        entry = library.set_review(str(rp), "phase-1.md", owner="agent-7", state="pending")
        # File + parent .awl dir now exist.
        assert rp.is_file()
        assert entry["owner"] == "agent-7"
        assert entry["state"] == "pending"
        assert "updated_at" in entry and isinstance(entry["updated_at"], str)

    def test_set_then_get_round_trips(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "phase-1.md", owner="agent-7", state="in_review",
                           verdict="revise", comments="tighten the scope")
        got = library.get_review(str(rp), "phase-1.md")
        assert got["owner"] == "agent-7"
        assert got["state"] == "in_review"
        assert got["verdict"] == "revise"
        assert got["comments"] == "tighten the scope"

    def test_partial_update_merges_only_provided_fields(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "phase-1.md", owner="agent-7", state="pending",
                           verdict="revise")
        first_stamp = library.get_review(str(rp), "phase-1.md")["updated_at"]
        # Update ONLY the state; owner + verdict must survive untouched.
        updated = library.set_review(str(rp), "phase-1.md", state="approved")
        assert updated["owner"] == "agent-7"      # preserved
        assert updated["verdict"] == "revise"      # preserved
        assert updated["state"] == "approved"      # changed
        # updated_at is re-stamped on every write (>= prior stamp).
        assert updated["updated_at"] >= first_stamp

    def test_owner_mapping_persists_across_loads(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "phase-1.md", owner="agent-7")
        library.set_review(str(rp), "phase-2.md", owner="agent-3")
        # Re-read from disk: the plan->owner mapping is intact for both plans.
        reviews = library.load_reviews(str(rp))
        assert reviews["phase-1.md"]["owner"] == "agent-7"
        assert reviews["phase-2.md"]["owner"] == "agent-3"

    def test_keyed_by_filename_independent_entries(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "a.md", owner="x", state="pending")
        library.set_review(str(rp), "b.md", owner="y", state="approved")
        # Touching b.md must not bleed into a.md.
        library.set_review(str(rp), "b.md", state="rejected")
        assert library.get_review(str(rp), "a.md")["state"] == "pending"
        assert library.get_review(str(rp), "b.md")["state"] == "rejected"

    def test_remove_existing_returns_true(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "phase-1.md", owner="agent-7")
        assert library.remove_review(str(rp), "phase-1.md") is True
        assert library.get_review(str(rp), "phase-1.md") is None

    def test_remove_missing_returns_false(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "phase-1.md", owner="agent-7")
        assert library.remove_review(str(rp), "ghost.md") is False
        # The real entry is untouched.
        assert library.get_review(str(rp), "phase-1.md") is not None

    def test_remove_on_missing_file_returns_false(self, tmp_path):
        rp = self._review_path(tmp_path)
        assert library.remove_review(str(rp), "phase-1.md") is False

    def test_stored_json_is_valid_object_keyed_by_filename(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "phase-1.md", owner="agent-7", state="pending")
        # The on-disk artifact is a JSON object keyed by the plan filename.
        raw = json.loads(rp.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        assert "phase-1.md" in raw
        assert raw["phase-1.md"]["owner"] == "agent-7"

    def test_none_values_do_not_overwrite_existing(self, tmp_path):
        rp = self._review_path(tmp_path)
        library.set_review(str(rp), "phase-1.md", owner="agent-7", state="pending")
        # Passing owner=None (the default) must NOT wipe the stored owner.
        updated = library.set_review(str(rp), "phase-1.md", state="approved")
        assert updated["owner"] == "agent-7"


# ---------------------------------------------------------------------------
# Thin cwd convenience wrappers (resolve the review path via storage)
# ---------------------------------------------------------------------------

class TestCwdWrappers:
    def test_set_and_get_review_for_cwd(self, tmp_path):
        proj = tmp_path / "myproj"
        proj.mkdir()
        cwd = str(proj)
        library.set_review_for_cwd(cwd, "phase-1.md", owner="agent-7", state="pending")
        # The legacy side-store lands at <project>/.awl-cc-dash/plan-reviews.json.
        assert (proj / ".awl-cc-dash" / "plan-reviews.json").is_file()
        got = library.get_review_for_cwd(cwd, "phase-1.md")
        assert got["owner"] == "agent-7"
        assert got["state"] == "pending"

    def test_load_reviews_for_cwd_missing_is_empty(self, tmp_path):
        proj = tmp_path / "myproj"
        proj.mkdir()
        assert library.load_reviews_for_cwd(str(proj)) == {}
