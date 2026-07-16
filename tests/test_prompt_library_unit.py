"""Hermetic unit tests for the prompt/UI-text markdown library (§7.14, §8.2, §8.4, §11 #45).

Decided contract (ARCHITECTURE §11 #45 — operator-decided 2026-07-15, which
OVERRIDES the plan file's scope model: nothing lives in ``~/.claude``):

One human-editable **markdown library** (`sidecar/prompt_library.py`) is the
single home for every UI-injected/canned text the dashboard sends on the user's
behalf, in the ``## group`` / ``### item`` convention, organized by purpose
(``responses.md`` · ``snippets.md`` · ``actions.md``). **Two scopes:** shipped
**defaults** committed in-repo at ``assets/prompts/`` (version-controlled,
travel with the product; edited as source, never through the API) and a
**project copy** at ``<project>/.awl-cc-dash/docs/prompts/`` (§8.2), with
**project-overrides-defaults** precedence, item-wise. A consumer whose item
exists in NEITHER scope degrades to its in-code fallback constant — the library
is never the reason a launch or a utility pass fails.

What this file pins (all pure Python — no WSL/tmux/network; the shipped
defaults are repo files, so reading them is hermetic):
  * ``parse_markdown`` — the ##/### convention: groups/items, verbatim bodies
    (outer blank LINES trimmed — a first content line keeps its indentation),
    header/group-preamble prose ignored, deeper or space-less hashes stay body
    text, items outside groups ignored, duplicate-item last-wins, empty body =
    present item with ``""``.
  * The **shipped defaults seed** — ``assets/prompts/`` carries the CURRENT
    hardcoded UI-injected texts VERBATIM (behavior-preserving): the #39
    Response (Structure) preset instructions (= the ``response_presets``
    catalog), the Revise/Summarize system texts (= ``utility_llm``'s
    constants), the attached-docs lead (= ``library.ATTACHED_DOCS_LEAD``), and
    the Compose snippet/template canned texts incl. the reviewer-request send
    text ("Code review request"). The handoff-report system text is the
    deliberate in-code-only exception (its body embeds ``## `` lines the
    format cannot hold).
  * **Precedence** — ``resolve``: project item wins (including a
    present-but-empty override), missing project item falls to defaults,
    missing everywhere returns the caller's default (``None``); ``resolved``
    merges item-wise.
  * **Consumer resolution + in-code fallback** — with the defaults dir pointed
    at an empty dir (``AWL_PROMPT_DEFAULTS``) and no project copy,
    ``response_presets.instruction_for`` / ``utility_llm.revise_system`` /
    ``summarize_system`` / ``library.attached_docs_preamble`` all still return
    their in-code texts. ``instruction_for(id, cwd=…)`` resolves a project
    override; the ``default`` preset stays a hard no-op (never
    library-overridable) and ids outside the in-code catalog stay unknown
    (``""``) even when a library item exists — the catalog is the menu/gate.
    The bridge driver launches with the cwd-resolved instruction.
  * **Project-scope write** — ``write_item`` targets ONLY
    ``docs/prompts/<file>`` (file inferred project-scope-first, then from the
    defaults' group→file map, or explicit for new groups), creates the store
    lazily, preserves sibling groups/items, rewrites atomically, purges the
    written group/key from every other project file (an item lives in exactly
    one file — a write can never be shadowed by a stale duplicate), and
    refuses unsafe file names, unknown groups without a file, multi-line
    group/key, bodies that would re-parse as ``##``/``###`` structure, and an
    undecodable (non-UTF-8) target file. Read-side robustness: an undecodable
    project file is skipped best-effort, never breaking sibling files or the
    defaults.
  * **Endpoints** — ``GET /prompt-library?scope=resolved|defaults|project``
    (400 on bad scope; 400 on project without cwd; resolved without cwd =
    defaults) and ``POST /prompt-library`` (project scope only; 400 via
    ``ValueError`` mapping); the utility endpoints pass their optional ``cwd``
    through to the scope-aware system-prompt resolution.

These carry neither the ``integration`` nor the ``slow`` mark.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import library  # noqa: E402
import prompt_library  # noqa: E402
import response_presets  # noqa: E402
import storage  # noqa: E402
import utility_llm  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from drivers.bridge import BridgeDriver  # noqa: E402


def _project(tmp_path: Path, name: str = "proj") -> str:
    """A tmp project dir with a .git marker so storage.project_root pins to it."""
    cwd = tmp_path / name
    (cwd / ".git").mkdir(parents=True)
    return str(cwd)


def _write_project_prompts(cwd: str, filename: str, text: str) -> Path:
    """Materialize a project-scope prompts file by hand (the read side never
    creates dirs — only write_item does)."""
    d = Path(cwd) / ".awl-cc-dash" / "docs" / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_markdown — the ##/### convention
# ---------------------------------------------------------------------------

class TestParseMarkdown:
    def test_groups_items_and_bodies(self):
        parsed = prompt_library.parse_markdown(
            "## alpha\n\n### one\n\nfirst text\n\n### two\n\nsecond text\n\n"
            "## beta\n\n### three\n\nthird text\n")
        assert parsed == {
            "alpha": {"one": "first text", "two": "second text"},
            "beta": {"three": "third text"},
        }

    def test_multiline_body_is_verbatim_inside(self):
        parsed = prompt_library.parse_markdown(
            "## g\n\n### i\n\nline one\n- bullet a\n- bullet b\n\nlast line\n")
        assert parsed["g"]["i"] == "line one\n- bullet a\n- bullet b\n\nlast line"

    def test_header_and_group_preamble_prose_ignored(self):
        parsed = prompt_library.parse_markdown(
            "# File header\n\nintro prose\n\n## g\n\ngroup preamble prose\n\n"
            "### i\n\nbody\n")
        assert parsed == {"g": {"i": "body"}}

    def test_deeper_and_spaceless_hashes_stay_body(self):
        parsed = prompt_library.parse_markdown(
            "## g\n\n### i\n\n#### deep heading\n##nospace\ntail\n")
        assert parsed["g"]["i"] == "#### deep heading\n##nospace\ntail"

    def test_outer_blank_lines_trim_but_indent_survives(self):
        # Only whole blank lines at the edges go — the first content line
        # keeps its indentation (a plain .strip() would de-indent it).
        parsed = prompt_library.parse_markdown(
            "## g\n\n### i\n\n\n    indented first\n    second\n\n")
        assert parsed["g"]["i"] == "    indented first\n    second"

    def test_item_outside_any_group_is_ignored(self):
        parsed = prompt_library.parse_markdown("### stray\n\ntext\n\n## g\n\n### i\n\nok\n")
        assert parsed == {"g": {"i": "ok"}}

    def test_duplicate_item_last_wins(self):
        parsed = prompt_library.parse_markdown(
            "## g\n\n### i\n\nfirst\n\n### i\n\nsecond\n")
        assert parsed["g"]["i"] == "second"

    def test_empty_body_is_a_present_item(self):
        parsed = prompt_library.parse_markdown("## g\n\n### i\n")
        assert parsed == {"g": {"i": ""}}

    def test_empty_and_headingless_text(self):
        assert prompt_library.parse_markdown("") == {}
        assert prompt_library.parse_markdown("just prose\n") == {}

    def test_crlf_normalizes(self):
        parsed = prompt_library.parse_markdown("## g\r\n\r\n### i\r\n\r\nbody\r\n")
        assert parsed == {"g": {"i": "body"}}

    def test_render_parse_round_trip(self):
        groups = {"g": {"i": "line one\n- b", "j": ""}, "h": {"k": "x"}}
        assert prompt_library.parse_markdown(
            prompt_library.render_markdown(groups)) == groups


# ---------------------------------------------------------------------------
# The shipped defaults seed — assets/prompts/ carries the CURRENT texts verbatim
# ---------------------------------------------------------------------------

class TestShippedDefaults:
    def test_default_files_exist(self):
        d = prompt_library.defaults_dir()
        for name in prompt_library.DEFAULT_FILES:
            assert (d / name).is_file(), f"missing shipped default {name}"

    def test_response_structure_items_match_catalog_verbatim(self):
        # Behavior-preserving: every non-default preset's library default IS
        # the in-code catalog instruction, character for character.
        for row in response_presets.catalog():
            pid = row["id"]
            if pid == response_presets.DEFAULT_PRESET:
                continue
            assert prompt_library.resolve("response-structure", pid) == \
                response_presets.get(pid)["instruction"], pid

    def test_default_preset_has_no_item(self):
        # The no-op is engine-side, deliberately absent from the files.
        assert prompt_library.resolve("response-structure", "default") is None

    def test_revise_and_summarize_match_utility_constants_verbatim(self):
        for key, text in utility_llm.REVISE_SYSTEMS.items():
            assert prompt_library.resolve("revise", key) == text, key
        assert prompt_library.resolve("summarize", "system") == \
            utility_llm.SUMMARIZE_SYSTEM

    def test_attached_docs_lead_matches_library_constant_verbatim(self):
        assert prompt_library.resolve("attached-docs", "lead") == \
            library.ATTACHED_DOCS_LEAD

    def test_handoff_system_stays_in_code_only(self):
        # Its body embeds "## " heading lines the ##/### format cannot hold.
        assert prompt_library.resolve("handoff", "report") is None
        assert "## What was being done" in utility_llm.HANDOFF_SYSTEM

    def test_compose_snippets_carry_the_canned_templates(self):
        snippets = prompt_library.load_defaults()["compose-snippets"]
        assert set(snippets) == {"Security audit request", "Code review request",
                                 "Refactor proposal", "Bug triage & severity"}
        # The reviewer-request send text, placeholders intact.
        review = snippets["Code review request"]
        assert review.startswith("Review the diff on {branch} for {focus}.")
        assert "{test_scope}" in review


# ---------------------------------------------------------------------------
# Precedence — project overrides defaults, item-wise; missing falls through
# ---------------------------------------------------------------------------

class TestPrecedence:
    def test_project_item_overrides_default(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### concise\n\nPROJECT SAYS SHORT.\n")
        assert prompt_library.resolve("response-structure", "concise", cwd) == \
            "PROJECT SAYS SHORT."
        # Without the cwd the shipped default still answers.
        assert prompt_library.resolve("response-structure", "concise") == \
            response_presets.get("concise")["instruction"]

    def test_missing_project_item_falls_to_defaults(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### concise\n\nPROJECT.\n")
        assert prompt_library.resolve("response-structure", "bullets", cwd) == \
            response_presets.get("bullets")["instruction"]

    def test_present_but_empty_project_item_is_a_real_override(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### concise\n")
        assert prompt_library.resolve("response-structure", "concise", cwd) == ""

    def test_missing_everywhere_returns_callers_default(self, tmp_path):
        cwd = _project(tmp_path)
        assert prompt_library.resolve("no-such-group", "x", cwd) is None
        assert prompt_library.resolve("no-such-group", "x", cwd,
                                      default="fallback") == "fallback"

    def test_project_only_group_resolves(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "extra.md", "## house\n\n### motto\n\nShip honest.\n")
        assert prompt_library.resolve("house", "motto", cwd) == "Ship honest."

    def test_resolved_merges_item_wise(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### concise\n\nPROJECT.\n")
        merged = prompt_library.resolved(cwd)["response-structure"]
        assert merged["concise"] == "PROJECT."             # overridden
        assert merged["bullets"] == \
            response_presets.get("bullets")["instruction"]  # untouched sibling

    def test_resolved_without_cwd_is_exactly_defaults(self):
        assert prompt_library.resolved(None) == prompt_library.load_defaults()

    def test_load_project_absent_store_is_empty(self, tmp_path):
        assert prompt_library.load_project(_project(tmp_path)) == {}

    def test_undecodable_project_file_is_skipped(self, tmp_path):
        # Reads are best-effort: one bad hand-save (cp1252/UTF-16) contributes
        # nothing but must never break sibling files or defaults resolution.
        cwd = _project(tmp_path)
        d = Path(cwd) / ".awl-cc-dash" / "docs" / "prompts"
        d.mkdir(parents=True)
        (d / "bad.md").write_bytes(
            b"## revise\n\n### grammar\n\nsmart \x92 quote\n")
        _write_project_prompts(cwd, "good.md",
                               "## house\n\n### motto\n\nShip honest.\n")
        assert prompt_library.resolve("house", "motto", cwd) == "Ship honest."
        assert prompt_library.resolve("revise", "grammar", cwd) == \
            utility_llm.REVISE_SYSTEMS["grammar"]
        assert "house" in prompt_library.load_project(cwd)
        assert "revise" not in prompt_library.load_project(cwd)


# ---------------------------------------------------------------------------
# Consumer resolution + the in-code fallback (both scopes absent)
# ---------------------------------------------------------------------------

class TestConsumerFallback:
    @pytest.fixture()
    def no_defaults(self, tmp_path, monkeypatch):
        """Point the shipped-defaults dir at an empty dir — no scope has items."""
        empty = tmp_path / "empty-defaults"
        empty.mkdir()
        monkeypatch.setenv("AWL_PROMPT_DEFAULTS", str(empty))

    def test_resolve_is_none_without_any_scope(self, no_defaults):
        assert prompt_library.resolve("response-structure", "tldr_table") is None

    def test_instruction_for_falls_back_to_catalog(self, no_defaults):
        assert response_presets.instruction_for("tldr_table") == \
            response_presets.get("tldr_table")["instruction"]

    def test_revise_and_summarize_fall_back_to_constants(self, no_defaults):
        assert utility_llm.revise_system("grammar") == \
            utility_llm.REVISE_SYSTEMS["grammar"]
        assert utility_llm.revise_system(None) == \
            utility_llm.REVISE_SYSTEMS["grammar"]
        assert utility_llm.summarize_system() == utility_llm.SUMMARIZE_SYSTEM

    def test_attached_docs_lead_falls_back(self, no_defaults, tmp_path):
        cwd = _project(tmp_path)
        doc = storage.ensure_docs_dir(cwd) / "a.md"
        doc.write_text("# doc", encoding="utf-8")
        text = library.attached_docs_preamble(cwd, ["a.md"])
        assert text.startswith(library.ATTACHED_DOCS_LEAD)


class TestPresetResolution:
    def test_shipped_default_and_catalog_agree_today(self):
        # Verbatim seeding means resolution through the library changes nothing.
        assert response_presets.instruction_for("tldr_table") == \
            response_presets.get("tldr_table")["instruction"]

    def test_project_override_reaches_instruction_for(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### tldr_table\n\nPROJECT FORMAT RULE.\n")
        assert response_presets.instruction_for("tldr_table", cwd=cwd) == \
            "PROJECT FORMAT RULE."
        # Other presets in the same project still fall to the shipped default.
        assert response_presets.instruction_for("concise", cwd=cwd) == \
            response_presets.get("concise")["instruction"]

    def test_empty_project_override_injects_nothing(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### tldr_table\n")
        assert response_presets.instruction_for("tldr_table", cwd=cwd) == ""

    def test_default_preset_is_never_library_overridable(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### default\n\nSHOUT EVERYTHING.\n")
        assert response_presets.instruction_for("default", cwd=cwd) == ""

    def test_ids_outside_the_catalog_stay_unknown(self, tmp_path):
        # The in-code catalog is the menu/gate — a project-only item under an
        # unknown id is never injected.
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### custom\n\nCUSTOM TEXT.\n")
        assert response_presets.instruction_for("custom", cwd=cwd) == ""
        assert response_presets.instruction_for(None, cwd=cwd) == ""

    def test_revise_system_takes_project_override(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "actions.md",
                               "## revise\n\n### grammar\n\nPROJECT COPY-EDIT RULES.\n")
        assert utility_llm.revise_system("grammar", cwd=cwd) == \
            "PROJECT COPY-EDIT RULES."
        assert utility_llm.revise_system("language", cwd=cwd) == \
            utility_llm.REVISE_SYSTEMS["language"]

    def test_summarize_system_takes_project_override(self, tmp_path):
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "actions.md",
                               "## summarize\n\n### system\n\nPROJECT SUMMARY RULES.\n")
        assert utility_llm.summarize_system(cwd=cwd) == "PROJECT SUMMARY RULES."
        # Without the cwd the shipped default (verbatim seed) still answers.
        assert utility_llm.summarize_system() == utility_llm.SUMMARIZE_SYSTEM

    def test_attached_docs_lead_takes_project_override(self, tmp_path):
        # The consumer path in library.attached_docs_preamble — not just
        # resolve() — must carry a project 'attached-docs/lead' override.
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "actions.md",
                               "## attached-docs\n\n### lead\n\nPROJECT LEAD LINE:\n")
        doc = storage.ensure_docs_dir(cwd) / "a.md"
        doc.write_text("# doc", encoding="utf-8")
        text = library.attached_docs_preamble(cwd, ["a.md"])
        assert text.startswith("PROJECT LEAD LINE:\n")
        assert library.ATTACHED_DOCS_LEAD not in text

    def test_driver_launch_carries_the_cwd_resolved_instruction(self, tmp_path, monkeypatch):
        # BridgeDriver._create_session resolves the preset against the agent's
        # OWN project copy (scripted-fake captured, never executed).
        cwd = _project(tmp_path)
        _write_project_prompts(cwd, "responses.md",
                               "## response-structure\n\n### tldr_table\n\nPROJECT FORMAT RULE.\n")
        d = BridgeDriver(DriverConfig(cwd=cwd, response_preset="tldr_table"),
                         lambda e: None)
        seen = {}

        def fake_create(name, **kw):
            seen.update(kw)
            return {"session_id": "deadbeef"}

        monkeypatch.setattr(d._bridge, "create", fake_create)
        d._create_session()
        assert seen["append_system_prompt"] == "PROJECT FORMAT RULE."


# ---------------------------------------------------------------------------
# write_item — the project-scope write
# ---------------------------------------------------------------------------

class TestWriteItem:
    def test_write_infers_file_from_defaults_and_round_trips(self, tmp_path):
        cwd = _project(tmp_path)
        out = prompt_library.write_item(cwd, "response-structure", "concise",
                                        "PROJECT SAYS SHORT.")
        assert out["file"] == "responses.md" and out["scope"] == "project"
        p = Path(cwd) / ".awl-cc-dash" / "docs" / "prompts" / "responses.md"
        assert Path(out["path"]) == p and p.is_file()
        assert prompt_library.resolve("response-structure", "concise", cwd) == \
            "PROJECT SAYS SHORT."

    def test_second_write_updates_and_preserves_siblings(self, tmp_path):
        cwd = _project(tmp_path)
        prompt_library.write_item(cwd, "response-structure", "concise", "ONE.")
        prompt_library.write_item(cwd, "response-structure", "bullets", "TWO.")
        prompt_library.write_item(cwd, "response-structure", "concise", "ONE-B.")
        proj = prompt_library.load_project(cwd)["response-structure"]
        assert proj == {"concise": "ONE-B.", "bullets": "TWO."}

    def test_unknown_group_requires_explicit_file(self, tmp_path):
        cwd = _project(tmp_path)
        with pytest.raises(ValueError, match="unknown group"):
            prompt_library.write_item(cwd, "house", "motto", "Ship honest.")
        out = prompt_library.write_item(cwd, "house", "motto", "Ship honest.",
                                        file="extra.md")
        assert out["file"] == "extra.md"
        assert prompt_library.resolve("house", "motto", cwd) == "Ship honest."

    def test_write_infers_file_from_the_project_scope(self, tmp_path):
        # A project-only group created earlier stays updatable WITHOUT
        # re-passing the file — inference consults the scope being written
        # first, then the shipped defaults.
        cwd = _project(tmp_path)
        prompt_library.write_item(cwd, "house", "motto", "v1", file="extra.md")
        out = prompt_library.write_item(cwd, "house", "tone", "Dry.")
        assert out["file"] == "extra.md"
        assert prompt_library.resolve("house", "tone", cwd) == "Dry."
        assert prompt_library.resolve("house", "motto", cwd) == "v1"

    def test_write_purges_stale_duplicates_in_other_files(self, tmp_path):
        # An item lives in exactly ONE project file: a write to aaa.md removes
        # the same group/key from zzz.md, so the sorted-name last-wins merge
        # can never shadow the write just made.
        cwd = _project(tmp_path)
        prompt_library.write_item(cwd, "house", "motto", "OLD", file="zzz.md")
        prompt_library.write_item(cwd, "house", "motto", "NEW", file="aaa.md")
        assert prompt_library.resolve("house", "motto", cwd) == "NEW"
        d = Path(cwd) / ".awl-cc-dash" / "docs" / "prompts"
        assert not (d / "zzz.md").exists()  # emptied by the purge -> removed

    def test_purge_preserves_other_items_in_the_old_file(self, tmp_path):
        cwd = _project(tmp_path)
        prompt_library.write_item(cwd, "house", "motto", "OLD", file="zzz.md")
        prompt_library.write_item(cwd, "house", "rules", "KEEP", file="zzz.md")
        prompt_library.write_item(cwd, "house", "motto", "NEW", file="aaa.md")
        assert prompt_library.resolve("house", "motto", cwd) == "NEW"
        assert prompt_library.resolve("house", "rules", cwd) == "KEEP"
        d = Path(cwd) / ".awl-cc-dash" / "docs" / "prompts"
        assert (d / "zzz.md").is_file()  # still carries house/rules

    def test_unsafe_file_names_refused(self, tmp_path):
        cwd = _project(tmp_path)
        for bad in ("../up.md", "a/b.md", "a\\b.md", "x.txt", ".hidden.md"):
            with pytest.raises(ValueError):
                prompt_library.write_item(cwd, "g", "k", "t", file=bad)

    def test_structure_lines_in_body_refused(self, tmp_path):
        cwd = _project(tmp_path)
        with pytest.raises(ValueError, match="heading lines"):
            prompt_library.write_item(cwd, "response-structure", "concise",
                                      "ok\n## sneaky group\nmore")
        with pytest.raises(ValueError, match="heading lines"):
            prompt_library.write_item(cwd, "response-structure", "concise",
                                      "### sneaky item")

    def test_whitespace_prefixed_heading_stays_verbatim_body(self, tmp_path):
        # ' ## x' is NOT structure (headings anchor at column 0), so it passes
        # the guard — and the write-side normalization must NOT promote it to
        # a real heading (the old .strip() did exactly that, minting a phantom
        # group and emptying the item behind a 200).
        cwd = _project(tmp_path)
        body = " ## My format\nAlways answer in tables."
        prompt_library.write_item(cwd, "response-structure", "tldr_table", body)
        assert prompt_library.resolve("response-structure", "tldr_table", cwd) == body
        assert set(prompt_library.load_project(cwd)) == {"response-structure"}
        assert response_presets.instruction_for("tldr_table", cwd=cwd) == body

    def test_indented_first_line_survives_verbatim(self, tmp_path):
        # Bodies are code-snippet-safe: only outer BLANK LINES trim, relative
        # indentation (including the first line's) survives the round trip.
        cwd = _project(tmp_path)
        body = "    indented code line\n    second line"
        prompt_library.write_item(cwd, "house", "snippet", body, file="extra.md")
        assert prompt_library.resolve("house", "snippet", cwd) == body

    def test_write_refuses_undecodable_target_file(self, tmp_path):
        # Never clobber a file we cannot read back: an undecodable target is a
        # ValueError (-> 400 through POST /prompt-library), file left intact.
        cwd = _project(tmp_path)
        d = Path(cwd) / ".awl-cc-dash" / "docs" / "prompts"
        d.mkdir(parents=True)
        raw = b"## house\n\n### motto\n\nsmart \x92 quote\n"
        (d / "extra.md").write_bytes(raw)
        with pytest.raises(ValueError, match="not valid UTF-8"):
            prompt_library.write_item(cwd, "house", "motto", "new", file="extra.md")
        assert (d / "extra.md").read_bytes() == raw

    def test_empty_or_multiline_group_key_refused(self, tmp_path):
        cwd = _project(tmp_path)
        with pytest.raises(ValueError):
            prompt_library.write_item(cwd, "", "k", "t", file="extra.md")
        with pytest.raises(ValueError):
            prompt_library.write_item(cwd, "g", "  ", "t", file="extra.md")
        with pytest.raises(ValueError):
            prompt_library.write_item(cwd, "g\nh", "k", "t", file="extra.md")

    def test_no_cwd_raises(self):
        with pytest.raises(ValueError):
            prompt_library.write_item(None, "response-structure", "concise", "t")

    def test_write_never_touches_the_shipped_defaults(self, tmp_path, monkeypatch):
        # The defaults dir content is byte-identical before and after a write.
        defaults = tmp_path / "defaults"
        defaults.mkdir()
        (defaults / "responses.md").write_text(
            "## response-structure\n\n### concise\n\nDEFAULT.\n", encoding="utf-8")
        monkeypatch.setenv("AWL_PROMPT_DEFAULTS", str(defaults))
        before = (defaults / "responses.md").read_text(encoding="utf-8")
        cwd = _project(tmp_path)
        prompt_library.write_item(cwd, "response-structure", "concise", "PROJECT.")
        assert (defaults / "responses.md").read_text(encoding="utf-8") == before
        assert prompt_library.resolve("response-structure", "concise", cwd) == "PROJECT."


# ---------------------------------------------------------------------------
# Endpoints — GET (three scopes) + POST (project-only write)
# ---------------------------------------------------------------------------

class TestEndpoints:
    @pytest.fixture(autouse=True)
    def _env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        import main
        self.main = main
        self.tmp_path = tmp_path

    def _get(self, **kw):
        return asyncio.run(self.main.get_prompt_library(**kw))

    def test_defaults_scope(self):
        out = self._get(scope="defaults")
        assert out["scope"] == "defaults"
        assert "response-structure" in out["groups"]
        assert out["groups"]["revise"]["grammar"] == \
            utility_llm.REVISE_SYSTEMS["grammar"]

    def test_resolved_without_cwd_is_defaults(self):
        assert self._get()["groups"] == self._get(scope="defaults")["groups"]

    def test_unknown_scope_is_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            self._get(scope="everything")
        assert ei.value.status_code == 400

    def test_project_scope_requires_cwd(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            self._get(scope="project")
        assert ei.value.status_code == 400

    def test_post_then_get_round_trip(self):
        cwd = _project(self.tmp_path)
        req = self.main.PromptLibraryWriteRequest(
            cwd=cwd, group="response-structure", key="concise", text="PROJECT.")
        out = asyncio.run(self.main.write_prompt_library(req))
        assert out["status"] == "written" and out["file"] == "responses.md"
        # Project scope shows exactly the write; resolved shows the override
        # layered over the untouched defaults.
        proj = self._get(scope="project", cwd=cwd)["groups"]
        assert proj == {"response-structure": {"concise": "PROJECT."}}
        merged = self._get(scope="resolved", cwd=cwd)["groups"]
        assert merged["response-structure"]["concise"] == "PROJECT."
        assert merged["response-structure"]["bullets"] == \
            response_presets.get("bullets")["instruction"]

    def test_post_invalid_write_maps_to_400(self):
        from fastapi import HTTPException
        cwd = _project(self.tmp_path)
        req = self.main.PromptLibraryWriteRequest(
            cwd=cwd, group="no-such-group", key="k", text="t")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(self.main.write_prompt_library(req))
        assert ei.value.status_code == 400

    def test_utility_endpoints_pass_cwd_through(self, monkeypatch):
        # The revise/summarize requests grew an optional cwd (§11 #45 project
        # scoping) — pin that the endpoints forward it to utility_llm.
        seen = {}

        async def fake_revise(text, scope, model, cwd):
            seen["revise"] = (text, scope, model, cwd)
            return "r"

        async def fake_summarize(text, model, cwd):
            seen["summarize"] = (text, model, cwd)
            return "s"

        monkeypatch.setattr(self.main.utility_llm, "revise", fake_revise)
        monkeypatch.setattr(self.main.utility_llm, "summarize", fake_summarize)
        cwd = _project(self.tmp_path)
        out = asyncio.run(self.main.utility_revise(
            self.main.ReviseRequest(text="t", scope="grammar", cwd=cwd)))
        assert out == {"scope": "grammar", "result": "r"}
        assert seen["revise"] == ("t", "grammar", None, cwd)
        out = asyncio.run(self.main.utility_summarize(
            self.main.SummarizeRequest(text="t", cwd=cwd)))
        assert out == {"result": "s"}
        assert seen["summarize"] == ("t", None, cwd)
