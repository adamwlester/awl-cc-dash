"""Hermetic unit tests for the Library module (read + render + per-doc sidecars).

Pure file logic — no driver, no WSL2/tmux, no live agent, no servers. Proves:

  * ``list_markdown`` enumerates ``.md`` files under a directory (optionally a
    ``plans`` subdir), with size + modified + base-relative ``rel_path``,
    skipping non-``.md`` and missing dirs. The default scan is flat/top-level
    (the browse-read-only project-root surface); ``recursive=True`` (§7.16 —
    the store's ``plans``/``docs`` collections) walks nested trees, entries
    sorted by ``rel_path`` (== the old ``filename`` sort for flat dirs). The
    recursive walk is **cycle-safe** — directory junctions/symlinks are never
    traversed (a self-junction lists each real doc exactly once and
    terminates; ``rglob`` would loop) — and ``exclude_top`` skips a named
    top-level subtree (the docs collection's §11 #45 ``prompts/`` copy)
    without touching same-named nested dirs.
  * ``read_document`` returns ``{filename, path, content}`` and raises on absent.
  * The LEGACY plan-review side-store (a JSON object keyed by plan FILENAME,
    carrying the plan↔agent owner mapping) round-trips through a real JSON file —
    set→get, partial-update merges fields, owner mapping persists, remove works,
    and ``load`` on a missing file is ``{}``. The function family is kept (it is
    the migration's reader) even though the endpoints now ride the sidecars.
  * **The per-doc metadata sidecar layer (§8.5)** — the store the review layer
    actually writes: ``<stem>.meta.json`` paired to ``<stem>.md``, never inside
    the content file. load/save round-trip with the skeleton on missing/corrupt;
    atomic write-replace (no ``.tmp`` residue); ``schema_version: 1`` stamped on
    every save; merge-don't-clobber review fields (+ ``verdict_by``/``verdict_at``);
    comments with unique ``c<N>`` ids, quote-anchors, and resolve; provenance
    with a first-write-stable ``created_at``; pair-rename (meta optional,
    overwrite refused, and a mid-pair meta-rename failure rolls the ``.md``
    back — never a half-renamed pair); orphan-detect + re-link; the legacy →
    sidecar migration (non-destructive — existing sidecar fields win; legacy
    file renamed ``.migrated``; idempotent); ``aggregate_metas``'s
    filename-keyed shape (plans/ + docs/ + the project ROOT's top-level metas,
    read-only, earlier dirs winning collisions — the store dirs walked
    **recursively** like the listing, so a comment on a nested doc surfaces
    instead of save-then-vanishing, with ``docs/prompts/`` excluded); and the
    WRITE-scope guards: mutations gate on ``document_in_content_dirs`` (only
    the store's ``plans/`` and ``docs/`` subtrees — ``state/``, bare
    store-root files, escapes, and outside-store paths refused), deletes
    operate on the ``resolve()``d path (alias spellings can't half-delete; the
    sidecar dies with its doc), and ``resolve_document_for_write`` never lands
    on the repo root — while it DOES find nested store docs (top level
    preferred) and never lands in ``docs/prompts/``.

Everything operates on ``tmp_path`` — never a real project dir. Sidecar-layer
project dirs get a ``.git`` marker so ``storage.project_root`` pins to the tmp
dir. These carry neither the ``integration`` nor the ``slow`` mark.
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

    def test_default_scan_stays_top_level(self, tmp_path):
        # The flat default (the browse-read-only root surface) must NOT walk
        # nested trees — recursion is opt-in for the store collections (§7.16).
        (tmp_path / "top.md").write_text("x", encoding="utf-8")
        nested = tmp_path / "phase-1"
        nested.mkdir()
        (nested / "plan.md").write_text("x", encoding="utf-8")
        names = {e["filename"] for e in library.list_markdown(str(tmp_path))}
        assert names == {"top.md"}

    def test_recursive_walks_nested_trees(self, tmp_path):
        # §7.16: the store's plans/docs collections may nest — recursive=True
        # lists the whole subtree, each entry carrying its base-relative
        # rel_path (POSIX separators).
        (tmp_path / "top.md").write_text("x", encoding="utf-8")
        deep = tmp_path / "phase-1" / "notes"
        deep.mkdir(parents=True)
        (deep / "plan.md").write_text("x", encoding="utf-8")
        entries = library.list_markdown(str(tmp_path), recursive=True)
        rels = [e["rel_path"] for e in entries]
        assert rels == ["phase-1/notes/plan.md", "top.md"]
        by_rel = {e["rel_path"]: e for e in entries}
        assert by_rel["phase-1/notes/plan.md"]["filename"] == "plan.md"
        assert Path(by_rel["phase-1/notes/plan.md"]["path"]) == deep / "plan.md"

    def test_recursive_skips_non_md_and_md_named_dirs(self, tmp_path):
        deep = tmp_path / "sub"
        deep.mkdir()
        (deep / "real.md").write_text("x", encoding="utf-8")
        (deep / "notes.txt").write_text("x", encoding="utf-8")
        (deep / "weird.md").mkdir()
        names = {e["filename"]
                 for e in library.list_markdown(str(tmp_path), recursive=True)}
        assert names == {"real.md"}

    def test_flat_entries_carry_rel_path_equal_to_filename(self, tmp_path):
        (tmp_path / "doc.md").write_text("x", encoding="utf-8")
        e = library.list_markdown(str(tmp_path))[0]
        assert e["rel_path"] == e["filename"] == "doc.md"

    @pytest.mark.skipif(sys.platform != "win32", reason="junctions are a Windows artifact")
    def test_recursive_walk_never_follows_junction_cycles(self, tmp_path):
        # Regression: Path.rglob on this Python follows directory junctions —
        # a single self-junction turned one real doc into dozens of phantom
        # rel_paths, and two junctions made GET /library/documents hang the
        # whole sidecar. The cycle-safe walk lists each REAL doc exactly once
        # and terminates (junctions are admin-free: any repo can contain one).
        import _winapi
        (tmp_path / "a.md").write_text("x", encoding="utf-8")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.md").write_text("x", encoding="utf-8")
        _winapi.CreateJunction(str(tmp_path), str(tmp_path / "loop"))
        _winapi.CreateJunction(str(tmp_path), str(sub / "loop2"))
        entries = library.list_markdown(str(tmp_path), recursive=True)
        assert [e["rel_path"] for e in entries] == ["a.md", "sub/b.md"]

    def test_recursive_exclude_top_skips_named_subtree(self, tmp_path):
        # exclude_top: the docs collection excludes its §11 #45 prompts/ copy —
        # prompt overrides are /prompt-library data, never Library documents.
        # Only the TOP-LEVEL subtree of that name is excluded; a nested dir
        # that happens to share the name still lists.
        (tmp_path / "team.md").write_text("x", encoding="utf-8")
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "actions.md").write_text("x", encoding="utf-8")
        nested = tmp_path / "guides" / "prompts"
        nested.mkdir(parents=True)
        (nested / "tips.md").write_text("x", encoding="utf-8")
        entries = library.list_markdown(str(tmp_path), recursive=True,
                                        exclude_top=("prompts",))
        assert [e["rel_path"] for e in entries] == ["guides/prompts/tips.md", "team.md"]


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


# ---------------------------------------------------------------------------
# Per-doc metadata sidecars (§8.5) — content + metadata as paired files
# ---------------------------------------------------------------------------

def _project(tmp_path):
    """A tmp project dir with a .git marker so storage.project_root pins here."""
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    return proj


def _md(dir_path, name="doc.md", body="# Doc\n"):
    dir_path.mkdir(parents=True, exist_ok=True)
    f = dir_path / name
    f.write_text(body, encoding="utf-8")
    return f


class TestMetaPath:
    def test_pairs_by_stem_next_to_the_md(self, tmp_path):
        assert (library.meta_path(tmp_path / "roadmap.md")
                == tmp_path / "roadmap.meta.json")

    def test_nested_dir_is_preserved(self, tmp_path):
        p = tmp_path / "plans" / "phase-1.md"
        assert library.meta_path(p) == tmp_path / "plans" / "phase-1.meta.json"


class TestLoadSaveMeta:
    def test_missing_sidecar_is_skeleton(self, tmp_path):
        meta = library.load_meta(tmp_path / "ghost.md")
        assert meta["schema_version"] == 1
        assert meta["review"] == {} and meta["comments"] == [] and meta["provenance"] == {}

    def test_corrupt_sidecar_degrades_to_skeleton(self, tmp_path):
        md = _md(tmp_path)
        library.meta_path(md).write_text("{not json", encoding="utf-8")
        assert library.load_meta(md)["comments"] == []

    def test_non_object_json_degrades_to_skeleton(self, tmp_path):
        md = _md(tmp_path)
        library.meta_path(md).write_text("[1, 2]", encoding="utf-8")
        assert library.load_meta(md)["review"] == {}

    def test_save_then_load_round_trips(self, tmp_path):
        md = _md(tmp_path)
        meta = library.load_meta(md)
        meta["review"]["owner"] = "coder-01"
        library.save_meta(md, meta)
        assert library.load_meta(md)["review"]["owner"] == "coder-01"

    def test_save_stamps_schema_version_and_updated_at(self, tmp_path):
        md = _md(tmp_path)
        saved = library.save_meta(md, {"review": {}, "comments": [], "provenance": {}})
        assert saved["schema_version"] == 1
        assert isinstance(saved["updated_at"], str) and "T" in saved["updated_at"]
        on_disk = json.loads(library.meta_path(md).read_text(encoding="utf-8"))
        assert on_disk["schema_version"] == 1 and "updated_at" in on_disk

    def test_atomic_write_leaves_no_tmp_residue(self, tmp_path):
        md = _md(tmp_path)
        library.save_meta(md, library.load_meta(md))
        assert library.meta_path(md).is_file()
        assert list(tmp_path.glob("*.tmp")) == []

    def test_failed_save_leaves_no_tmp_and_keeps_prior_content(self, tmp_path):
        md = _md(tmp_path)
        library.save_meta(md, {"review": {"owner": "keep-me"},
                               "comments": [], "provenance": {}})
        with pytest.raises(TypeError):  # a set is not JSON-serializable
            library.save_meta(md, {"review": {"bad": {1, 2}},
                                   "comments": [], "provenance": {}})
        assert list(tmp_path.glob("*.tmp")) == []
        assert library.load_meta(md)["review"]["owner"] == "keep-me"  # torn write never lands


class TestSetDocReview:
    def test_creates_sidecar_next_to_doc(self, tmp_path):
        md = _md(tmp_path, "roadmap.md")
        library.set_doc_review(md, owner="coder-01", state="in_review")
        assert (tmp_path / "roadmap.meta.json").is_file()
        review = library.load_meta(md)["review"]
        assert review["owner"] == "coder-01" and review["state"] == "in_review"

    def test_merge_does_not_clobber_unset_fields(self, tmp_path):
        md = _md(tmp_path)
        library.set_doc_review(md, owner="coder-01", state="pending")
        library.set_doc_review(md, state="approved")   # owner not passed
        review = library.load_meta(md)["review"]
        assert review["owner"] == "coder-01"           # preserved
        assert review["state"] == "approved"           # changed

    def test_verdict_stamps_who_and_when(self, tmp_path):
        md = _md(tmp_path)
        library.set_doc_review(md, verdict="approve", verdict_by="user")
        review = library.load_meta(md)["review"]
        assert review["verdict"] == "approve"
        assert review["verdict_by"] == "user"
        assert isinstance(review["verdict_at"], str) and "T" in review["verdict_at"]

    def test_no_verdict_means_no_verdict_at_restamp(self, tmp_path):
        md = _md(tmp_path)
        library.set_doc_review(md, verdict="approve", verdict_by="user")
        stamp = library.load_meta(md)["review"]["verdict_at"]
        library.set_doc_review(md, state="done")       # no verdict passed
        assert library.load_meta(md)["review"]["verdict_at"] == stamp


class TestComments:
    def test_ids_run_c1_c2_unique_per_sidecar(self, tmp_path):
        md = _md(tmp_path)
        assert library.add_comment(md, text="first", author="user")["id"] == "c1"
        assert library.add_comment(md, text="second", author="user")["id"] == "c2"
        other = _md(tmp_path, "other.md")
        assert library.add_comment(other, text="own seq", author="user")["id"] == "c1"

    def test_anchor_quote_and_heading_are_stored(self, tmp_path):
        md = _md(tmp_path)
        c = library.add_comment(md, text="tighten this", author="user",
                                anchor_quote="the exact quoted snippet",
                                anchor_heading="Goals")
        stored = library.load_meta(md)["comments"][0]
        assert stored["anchor_quote"] == "the exact quoted snippet"
        assert stored["anchor_heading"] == "Goals"
        assert stored["id"] == c["id"]

    def test_doc_level_comment_has_null_anchors(self, tmp_path):
        md = _md(tmp_path)
        library.add_comment(md, text="no anchor", author="user")
        stored = library.load_meta(md)["comments"][0]
        assert stored["anchor_quote"] is None and stored["anchor_heading"] is None

    def test_comment_shape(self, tmp_path):
        md = _md(tmp_path)
        c = library.add_comment(md, text="hello", author="coder-01")
        assert c["text"] == "hello" and c["author"] == "coder-01"
        assert c["resolved"] is False
        assert isinstance(c["ts"], str) and "T" in c["ts"]

    def test_resolve_flips_flag_and_persists(self, tmp_path):
        md = _md(tmp_path)
        library.add_comment(md, text="fix me", author="user")
        assert library.resolve_comment(md, "c1") is True
        assert library.load_meta(md)["comments"][0]["resolved"] is True

    def test_resolve_unknown_id_is_false(self, tmp_path):
        md = _md(tmp_path)
        library.add_comment(md, text="x", author="user")
        assert library.resolve_comment(md, "c99") is False

    def test_ids_stay_unique_after_resolve(self, tmp_path):
        md = _md(tmp_path)
        library.add_comment(md, text="a", author="user")
        library.resolve_comment(md, "c1")
        assert library.add_comment(md, text="b", author="user")["id"] == "c2"


class TestProvenance:
    def test_created_at_stamped_on_first_write(self, tmp_path):
        md = _md(tmp_path)
        library.set_provenance(md, created_by="coder-01", session="sess-1")
        prov = library.load_meta(md)["provenance"]
        assert prov["created_by"] == "coder-01" and prov["session"] == "sess-1"
        assert isinstance(prov["created_at"], str) and "T" in prov["created_at"]

    def test_created_at_never_restamped(self, tmp_path):
        md = _md(tmp_path)
        library.set_provenance(md, created_by="coder-01")
        # Pin created_at to a sentinel, then write provenance again: the
        # sentinel must survive (created_at records first entry, not last touch).
        meta = library.load_meta(md)
        meta["provenance"]["created_at"] = "2020-01-01T00:00:00+00:00"
        library.save_meta(md, meta)
        library.set_provenance(md, session="sess-2")
        prov = library.load_meta(md)["provenance"]
        assert prov["created_at"] == "2020-01-01T00:00:00+00:00"
        assert prov["created_by"] == "coder-01" and prov["session"] == "sess-2"


class TestRenameDocumentPair:
    def test_renames_md_and_meta_together(self, tmp_path):
        md = _md(tmp_path, "draft.md")
        library.set_doc_review(md, owner="coder-01")
        out = library.rename_document_pair(md, "final.md")
        assert not md.exists() and not (tmp_path / "draft.meta.json").exists()
        assert (tmp_path / "final.md").is_file()
        assert (tmp_path / "final.meta.json").is_file()
        assert library.load_meta(tmp_path / "final.md")["review"]["owner"] == "coder-01"
        assert out == {"old": str(md), "new": str(tmp_path / "final.md")}

    def test_meta_may_be_absent(self, tmp_path):
        md = _md(tmp_path, "bare.md")
        library.rename_document_pair(md, "renamed.md")
        assert (tmp_path / "renamed.md").is_file()
        assert not (tmp_path / "renamed.meta.json").exists()

    def test_refuses_overwriting_existing_md(self, tmp_path):
        md = _md(tmp_path, "a.md")
        _md(tmp_path, "b.md")
        with pytest.raises(FileExistsError):
            library.rename_document_pair(md, "b.md")
        assert md.is_file()  # nothing moved

    def test_refuses_overwriting_existing_meta(self, tmp_path):
        md = _md(tmp_path, "a.md")
        library.set_doc_review(md, owner="x")           # a.meta.json exists
        (tmp_path / "b.meta.json").write_text("{}", encoding="utf-8")
        with pytest.raises(FileExistsError):
            library.rename_document_pair(md, "b.md")
        assert md.is_file() and (tmp_path / "a.meta.json").is_file()  # pair intact

    def test_missing_source_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            library.rename_document_pair(tmp_path / "ghost.md", "x.md")

    def test_rejects_separators_in_new_name(self, tmp_path):
        md = _md(tmp_path)
        with pytest.raises(ValueError):
            library.rename_document_pair(md, "../escape.md")

    def test_meta_rename_failure_rolls_the_md_back(self, tmp_path, monkeypatch):
        """If the SECOND rename (the sidecar) fails, the first (the .md) is
        rolled back — a pair is never left half-renamed."""
        md = _md(tmp_path, "draft.md")
        library.set_doc_review(md, owner="coder-01")
        real_rename = Path.rename

        def failing(self, target):
            if self.name.endswith(".meta.json"):
                raise OSError("simulated: meta locked")
            return real_rename(self, target)

        monkeypatch.setattr(Path, "rename", failing)
        with pytest.raises(OSError):
            library.rename_document_pair(md, "final.md")
        # The pair is intact under its ORIGINAL name; nothing half-moved.
        assert md.is_file()
        assert (tmp_path / "draft.meta.json").is_file()
        assert not (tmp_path / "final.md").exists()
        assert not (tmp_path / "final.meta.json").exists()


class TestOrphanMetas:
    def test_detects_only_unpaired_metas(self, tmp_path):
        md = _md(tmp_path, "paired.md")
        library.set_doc_review(md, owner="x")
        (tmp_path / "orphan.meta.json").write_text("{}", encoding="utf-8")
        assert library.find_orphan_metas(tmp_path) == [str(tmp_path / "orphan.meta.json")]

    def test_missing_dir_is_empty(self, tmp_path):
        assert library.find_orphan_metas(tmp_path / "nope") == []

    def test_relink_renames_meta_into_pair_position(self, tmp_path):
        orphan = tmp_path / "old-name.meta.json"
        orphan.write_text(json.dumps({"review": {"owner": "x"}}), encoding="utf-8")
        md = _md(tmp_path, "new-name.md")
        assert library.relink_meta(orphan, md) is True
        assert not orphan.exists()
        assert library.load_meta(md)["review"]["owner"] == "x"

    def test_relink_refuses_when_target_already_has_meta(self, tmp_path):
        orphan = tmp_path / "orphan.meta.json"
        orphan.write_text("{}", encoding="utf-8")
        md = _md(tmp_path, "doc.md")
        library.set_doc_review(md, owner="keep")
        assert library.relink_meta(orphan, md) is False
        assert orphan.exists()                          # untouched
        assert library.load_meta(md)["review"]["owner"] == "keep"

    def test_relink_to_missing_md_is_false(self, tmp_path):
        orphan = tmp_path / "orphan.meta.json"
        orphan.write_text("{}", encoding="utf-8")
        assert library.relink_meta(orphan, tmp_path / "ghost.md") is False

    def test_relink_already_paired_is_true(self, tmp_path):
        md = _md(tmp_path, "doc.md")
        library.set_doc_review(md, owner="x")
        assert library.relink_meta(library.meta_path(md), md) is True


class TestMigratePlanReviews:
    def _legacy(self, proj, entries):
        store = proj / ".awl-cc-dash"
        store.mkdir(parents=True, exist_ok=True)
        (store / "plan-reviews.json").write_text(
            json.dumps(entries), encoding="utf-8")
        return store / "plan-reviews.json"

    def test_entry_lands_next_to_plans_md(self, tmp_path):
        proj = _project(tmp_path)
        _md(proj / ".awl-cc-dash" / "plans", "phase-1.md")
        self._legacy(proj, {"phase-1.md": {"owner": "coder-01", "state": "pending"}})
        assert library.migrate_plan_reviews(str(proj)) == 1
        meta = library.load_meta(proj / ".awl-cc-dash" / "plans" / "phase-1.md")
        assert meta["review"]["owner"] == "coder-01"
        assert meta["review"]["state"] == "pending"

    def test_entry_matches_project_root_md_second(self, tmp_path):
        # The legacy store keyed bare filenames from the old flat layout — a doc
        # still at the project root pairs there when plans/ has no match.
        proj = _project(tmp_path)
        _md(proj, "rootplan.md")
        self._legacy(proj, {"rootplan.md": {"owner": "coder-02"}})
        library.migrate_plan_reviews(str(proj))
        assert (proj / "rootplan.meta.json").is_file()
        assert library.load_meta(proj / "rootplan.md")["review"]["owner"] == "coder-02"

    def test_unmatched_entry_becomes_plans_orphan(self, tmp_path):
        # No .md anywhere: the sidecar is still written (in plans/) rather than
        # dropping review data — it surfaces as a detectable, re-linkable orphan.
        proj = _project(tmp_path)
        self._legacy(proj, {"ghost.md": {"owner": "coder-03"}})
        library.migrate_plan_reviews(str(proj))
        plans = proj / ".awl-cc-dash" / "plans"
        assert (plans / "ghost.meta.json").is_file()
        assert library.find_orphan_metas(plans) == [str(plans / "ghost.meta.json")]

    def test_existing_sidecar_fields_win(self, tmp_path):
        proj = _project(tmp_path)
        md = _md(proj / ".awl-cc-dash" / "plans", "phase-1.md")
        library.set_doc_review(md, owner="sidecar-owner")
        library.add_comment(md, text="sidecar comment", author="user")
        self._legacy(proj, {"phase-1.md": {"owner": "legacy-owner",
                                           "state": "pending",
                                           "comments": "legacy note"}})
        library.migrate_plan_reviews(str(proj))
        meta = library.load_meta(md)
        assert meta["review"]["owner"] == "sidecar-owner"   # sidecar wins
        assert meta["review"]["state"] == "pending"          # absent field filled
        # The sidecar already had comments -> legacy comments are NOT appended.
        assert [c["text"] for c in meta["comments"]] == ["sidecar comment"]

    def test_legacy_string_comments_become_a_comment(self, tmp_path):
        proj = _project(tmp_path)
        md = _md(proj / ".awl-cc-dash" / "plans", "phase-1.md")
        self._legacy(proj, {"phase-1.md": {"owner": "coder-01",
                                           "comments": "tighten the scope"}})
        library.migrate_plan_reviews(str(proj))
        comments = library.load_meta(md)["comments"]
        assert len(comments) == 1
        assert comments[0]["id"] == "c1"
        assert comments[0]["text"] == "tighten the scope"
        assert comments[0]["author"] == "coder-01"          # falls back to owner
        assert comments[0]["resolved"] is False

    def test_legacy_file_renamed_migrated_and_idempotent(self, tmp_path):
        proj = _project(tmp_path)
        md = _md(proj / ".awl-cc-dash" / "plans", "phase-1.md")
        legacy = self._legacy(proj, {"phase-1.md": {"comments": "note"}})
        assert library.migrate_plan_reviews(str(proj)) == 1
        assert not legacy.exists()
        assert legacy.with_name("plan-reviews.json.migrated").is_file()
        # Second run: no legacy file -> no-op, nothing re-applied.
        assert library.migrate_plan_reviews(str(proj)) == 0
        assert len(library.load_meta(md)["comments"]) == 1

    def test_no_legacy_file_is_noop(self, tmp_path):
        proj = _project(tmp_path)
        assert library.migrate_plan_reviews(str(proj)) == 0


class TestAggregateMetas:
    def test_filename_keyed_union_of_plans_and_docs(self, tmp_path):
        proj = _project(tmp_path)
        plan = _md(proj / ".awl-cc-dash" / "plans", "roadmap.md")
        doc = _md(proj / ".awl-cc-dash" / "docs", "notes.md")
        library.set_doc_review(plan, owner="a")
        library.set_doc_review(doc, owner="b")
        agg = library.aggregate_metas(str(proj))
        assert set(agg.keys()) == {"roadmap.md", "notes.md"}
        assert agg["roadmap.md"]["review"]["owner"] == "a"
        assert agg["notes.md"]["review"]["owner"] == "b"
        assert agg["notes.md"]["schema_version"] == 1

    def test_docs_without_sidecars_do_not_appear(self, tmp_path):
        proj = _project(tmp_path)
        _md(proj / ".awl-cc-dash" / "plans", "bare.md")   # no sidecar written
        assert library.aggregate_metas(str(proj)) == {}

    def test_root_level_metas_are_aggregated_read_only(self, tmp_path):
        # A migrated root-doc review (rootplan.meta.json at the project ROOT —
        # the migration's recorded root-seam behavior) must stay visible in the
        # aggregate, not silently invisible.
        proj = _project(tmp_path)
        root_md = _md(proj, "rootplan.md")
        library.set_doc_review(root_md, owner="coder-02")
        agg = library.aggregate_metas(str(proj))
        assert agg["rootplan.md"]["review"]["owner"] == "coder-02"

    def test_store_dirs_win_root_on_name_collision(self, tmp_path):
        proj = _project(tmp_path)
        plan = _md(proj / ".awl-cc-dash" / "plans", "x.md")
        root = _md(proj, "x.md")
        library.set_doc_review(plan, owner="plans-owner")
        library.set_doc_review(root, owner="root-owner")
        agg = library.aggregate_metas(str(proj))
        assert agg["x.md"]["review"]["owner"] == "plans-owner"

    def test_empty_project_is_empty(self, tmp_path):
        assert library.aggregate_metas(str(_project(tmp_path))) == {}

    def test_nested_doc_sidecars_surface_recursively(self, tmp_path):
        # Regression (save-then-vanish): the recursive listing offers nested
        # docs and comments on them save fine — so the reviews aggregate must
        # walk the same subtrees, or a saved comment silently disappears from
        # GET /library/reviews.
        proj = _project(tmp_path)
        nested = _md(proj / ".awl-cc-dash" / "docs" / "guides", "howto.md")
        library.add_comment(nested, text="nice", author="op")
        agg = library.aggregate_metas(str(proj))
        assert agg["howto.md"]["comments"][0]["text"] == "nice"

    def test_docs_prompts_subtree_excluded_from_aggregate(self, tmp_path):
        # The §11 #45 prompt-library copy (docs/prompts/) is another surface's
        # data — its sidecars (if any ever appear) stay out of the reviews
        # aggregate, matching the listing's exclusion.
        proj = _project(tmp_path)
        item = _md(proj / ".awl-cc-dash" / "docs" / "prompts", "actions.md")
        library.set_doc_review(item, owner="x")
        assert library.aggregate_metas(str(proj)) == {}


class TestCreateDeleteDocument:
    def test_create_defaults_to_docs(self, tmp_path):
        proj = _project(tmp_path)
        out = library.create_document(str(proj), "notes.md", "# Notes\n")
        target = proj / ".awl-cc-dash" / "docs" / "notes.md"
        assert target.is_file()
        assert target.read_text(encoding="utf-8") == "# Notes\n"
        assert out["filename"] == "notes.md" and out["subdir"] == "docs"

    def test_create_in_plans(self, tmp_path):
        proj = _project(tmp_path)
        library.create_document(str(proj), "phase-1.md", "plan", subdir="plans")
        assert (proj / ".awl-cc-dash" / "plans" / "phase-1.md").is_file()

    def test_create_refuses_existing(self, tmp_path):
        proj = _project(tmp_path)
        library.create_document(str(proj), "notes.md", "one")
        with pytest.raises(FileExistsError):
            library.create_document(str(proj), "notes.md", "two")

    def test_create_rejects_path_escapes(self, tmp_path):
        proj = _project(tmp_path)
        for bad in ("a/b.md", "a\\b.md", "..\\evil.md", "../evil.md", "..md"):
            with pytest.raises(ValueError):
                library.create_document(str(proj), bad, "x")

    def test_create_rejects_non_md_and_bad_subdir(self, tmp_path):
        proj = _project(tmp_path)
        with pytest.raises(ValueError):
            library.create_document(str(proj), "notes.txt", "x")
        with pytest.raises(ValueError):
            library.create_document(str(proj), "notes.md", "x", subdir="assets")

    def test_delete_removes_md_and_paired_meta(self, tmp_path):
        proj = _project(tmp_path)
        out = library.create_document(str(proj), "gone.md", "x")
        library.set_doc_review(out["path"], owner="a")
        result = library.delete_document(out["path"], str(proj))
        assert not Path(out["path"]).exists()
        assert not library.meta_path(out["path"]).exists()
        assert len(result["deleted"]) == 2

    def test_delete_refuses_paths_outside_the_store(self, tmp_path):
        proj = _project(tmp_path)
        outside = _md(proj, "readme.md")           # project root, NOT the store
        with pytest.raises(ValueError):
            library.delete_document(str(outside), str(proj))
        assert outside.is_file()                   # untouched

    def test_delete_refuses_dotdot_escape_from_store(self, tmp_path):
        proj = _project(tmp_path)
        outside = _md(proj, "readme.md")
        sneaky = proj / ".awl-cc-dash" / "docs" / ".." / ".." / "readme.md"
        with pytest.raises(ValueError):
            library.delete_document(str(sneaky), str(proj))
        assert outside.is_file()

    def test_delete_missing_raises_not_found(self, tmp_path):
        proj = _project(tmp_path)
        (proj / ".awl-cc-dash" / "docs").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            library.delete_document(str(proj / ".awl-cc-dash" / "docs" / "ghost.md"),
                                    str(proj))

    def test_delete_refuses_non_md_targets(self, tmp_path):
        proj = _project(tmp_path)
        out = library.create_document(str(proj), "doc.md", "x")
        library.set_doc_review(out["path"], owner="a")
        with pytest.raises(ValueError):   # the sidecar is not addressed directly
            library.delete_document(str(library.meta_path(out["path"])), str(proj))

    def test_delete_refuses_state_and_store_root_files(self, tmp_path):
        # Mutations are scoped to the store's plans/+docs/ CONTENT dirs only —
        # state/ (the dashboard's JSON state) and bare store-root files are
        # off-limits even though they sit inside .awl-cc-dash/.
        proj = _project(tmp_path)
        state_md = _md(proj / ".awl-cc-dash" / "state", "agents.md")
        root_md = _md(proj / ".awl-cc-dash", "loose.md")
        with pytest.raises(ValueError):
            library.delete_document(str(state_md), str(proj))
        with pytest.raises(ValueError):
            library.delete_document(str(root_md), str(proj))
        assert state_md.is_file() and root_md.is_file()

    def test_delete_operates_on_the_resolved_path(self, tmp_path):
        # An alias spelling of the doc (here its Windows 8.3 short name; a
        # symlink behaves the same) must not half-delete the pair: resolve()
        # first, then unlink + meta pairing on the REAL path.
        import ctypes
        proj = _project(tmp_path)
        md = _md(proj / ".awl-cc-dash" / "docs", "longdocumentname.md")
        library.set_doc_review(md, owner="a")
        meta = library.meta_path(md)
        buf = ctypes.create_unicode_buffer(520)
        rc = ctypes.windll.kernel32.GetShortPathNameW(str(md), buf, 520)
        alias = buf.value
        if not rc or alias.lower() == str(md).lower():
            pytest.skip("8.3 short names unavailable on this volume")
        out = library.delete_document(alias, str(proj))
        assert not md.exists()
        assert not meta.exists()          # the sidecar died with its doc
        assert len(out["deleted"]) == 2


class TestResolveDocumentAndScope:
    def test_priority_plans_then_docs_then_root(self, tmp_path):
        proj = _project(tmp_path)
        _md(proj, "x.md", "root")
        assert library.resolve_document(str(proj), "x.md") == proj / "x.md"
        _md(proj / ".awl-cc-dash" / "docs", "x.md", "docs")
        assert (library.resolve_document(str(proj), "x.md")
                == proj / ".awl-cc-dash" / "docs" / "x.md")
        _md(proj / ".awl-cc-dash" / "plans", "x.md", "plans")
        assert (library.resolve_document(str(proj), "x.md")
                == proj / ".awl-cc-dash" / "plans" / "x.md")

    def test_missing_everywhere_is_none(self, tmp_path):
        assert library.resolve_document(str(_project(tmp_path)), "ghost.md") is None

    def test_rejects_separators(self, tmp_path):
        with pytest.raises(ValueError):
            library.resolve_document(str(_project(tmp_path)), "../../etc.md")

    def test_document_in_store_boundaries(self, tmp_path):
        proj = _project(tmp_path)
        inside = proj / ".awl-cc-dash" / "docs" / "in.md"
        outside = proj / "out.md"
        escape = proj / ".awl-cc-dash" / ".." / "out.md"  # resolves outside
        assert library.document_in_store(str(inside), str(proj)) is True
        assert library.document_in_store(str(outside), str(proj)) is False
        assert library.document_in_store(str(escape), str(proj)) is False

    def test_document_in_content_dirs_boundaries(self, tmp_path):
        # The WRITE gate: only plans/ and docs/ subtrees pass — state/, bare
        # store-root files, and everything outside the store are refused.
        proj = _project(tmp_path)
        store = proj / ".awl-cc-dash"
        assert library.document_in_content_dirs(
            str(store / "docs" / "in.md"), str(proj)) is True
        assert library.document_in_content_dirs(
            str(store / "plans" / "p.md"), str(proj)) is True
        assert library.document_in_content_dirs(
            str(store / "plans" / "nested" / "deep.md"), str(proj)) is True
        assert library.document_in_content_dirs(
            str(store / "state" / "agents.json"), str(proj)) is False
        assert library.document_in_content_dirs(
            str(store / "loose.md"), str(proj)) is False
        assert library.document_in_content_dirs(
            str(proj / "out.md"), str(proj)) is False
        assert library.document_in_content_dirs(
            str(store / "docs" / ".." / ".." / "out.md"), str(proj)) is False

    def test_resolve_document_for_write_skips_the_project_root(self, tmp_path):
        # Write-side resolution never lands on the repo root: a root-only doc
        # is None (no sidecar minted there); a store copy resolves normally.
        proj = _project(tmp_path)
        _md(proj, "x.md", "root")
        assert library.resolve_document_for_write(str(proj), "x.md") is None
        _md(proj / ".awl-cc-dash" / "docs", "x.md", "docs")
        assert (library.resolve_document_for_write(str(proj), "x.md")
                == proj / ".awl-cc-dash" / "docs" / "x.md")

    def test_resolve_for_write_finds_nested_docs(self, tmp_path):
        # §7.16 consistency: a nested doc the recursive listing offers must
        # also resolve for review/comment writes — never list-then-404.
        proj = _project(tmp_path)
        nested = _md(proj / ".awl-cc-dash" / "docs" / "guides", "howto.md")
        assert library.resolve_document_for_write(str(proj), "howto.md") == nested
        assert library.resolve_document(str(proj), "howto.md") == nested

    def test_resolve_prefers_top_level_over_nested(self, tmp_path):
        proj = _project(tmp_path)
        _md(proj / ".awl-cc-dash" / "docs" / "guides", "x.md", "nested")
        top = _md(proj / ".awl-cc-dash" / "docs", "x.md", "top")
        assert library.resolve_document_for_write(str(proj), "x.md") == top

    def test_resolve_for_write_never_lands_in_docs_prompts(self, tmp_path):
        # The §11 #45 prompt copy is not a reviewable document: a filename
        # that exists ONLY there resolves None (its surface is /prompt-library).
        proj = _project(tmp_path)
        _md(proj / ".awl-cc-dash" / "docs" / "prompts", "actions.md")
        assert library.resolve_document_for_write(str(proj), "actions.md") is None
