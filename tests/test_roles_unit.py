"""Hermetic unit tests — the two-scope agent.md role catalog (DESIGN.md ND 12).

The decided contract this file encodes:

  * ``GET /roles?cwd=`` returns the TWO-scope catalog the Create Role combobox
    renders: ``system`` = ``~/.claude/agents`` (surfaced, not owned;
    ``AWL_SYSTEM_AGENTS_DIR`` overrides — resolved per call, so the unit tier
    is hermetic) and ``project`` = ``<project>/.awl-cc-dash/agents/``
    (``storage.agents_dir``, §8.2). Group labels reproduce the mockup's
    ROLE_DEFS header strings exactly. No ``cwd`` (or no project home) →
    ``project.dir: null`` + empty roles — the honest degrade, mirroring the
    prompt library's no-project read.
  * **Front matter is hand-parsed** (no PyYAML — the observed corpus is a
    shallow subset): ``---`` fences; ``key: value`` scalars; inline comma
    lists (``tools: Read, Glob, mcp__x__*``); YAML block lists (``skills:`` +
    ``- item`` lines at ANY indent, zero-indent included); ``#``-commented
    lines ignored (a ``#model: fable`` never shadows the live ``model:``); a
    file with no front matter at all is ``({}, body)``. Missing ``name``
    falls back to the filename stem.
  * **The wire payload is snake_case** like the rest of the sidecar API:
    ``permission_mode`` / ``max_turns`` — parsed FROM the camelCase agent.md
    front-matter spellings (``permissionMode`` / ``maxTurns``), which stay
    the file convention.
  * **Color carries BOTH forms**: ``color`` is the raw front-matter value;
    ``color_hex`` is a raw ``#rrggbb`` passthrough, a named-color map into the
    AG_COLORS hexes (Claude Code's named set + the AG_COLORS names
    themselves), else ``None``.
  * The listing payload is LIGHT — front-matter fields + ``file`` (absolute)
    + ``scope``, NO markdown body; roles sort by name; non-``.md`` files are
    ignored; an unreadable file is skipped, never fatal.

No WSL, no network — tmp_path fixtures; the endpoint is driven directly via
``asyncio.run`` (the suite's unit-tier convention).
"""

import asyncio
import sys
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import roles  # noqa: E402
import storage  # noqa: E402
import main  # noqa: E402
from identity import AG_COLORS  # noqa: E402

_AG = dict(AG_COLORS)


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
    yield


def _write(directory: Path, name: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / name
    p.write_text(text, encoding="utf-8")
    return p


_FULL_MD = """---
name: echo
description: Session distiller and brief writer
tools: Read, Glob, mcp__context7__*
model: opus
#model: fable
color: purple
permissionMode: acceptEdits
maxTurns: 25
effort: max
skills:
  - distill
  - session-brief
---

You are echo. Distill the session.
"""


# ---------------------------------------------------------------------------
# Front-matter parser
# ---------------------------------------------------------------------------

class TestParseFrontMatter:
    def test_full_front_matter_all_keys(self):
        fm, body = roles.parse_front_matter(_FULL_MD)
        assert fm["name"] == "echo"
        assert fm["description"] == "Session distiller and brief writer"
        # Inline comma list, wildcard entry intact.
        assert fm["tools"] == ["Read", "Glob", "mcp__context7__*"]
        # Block list.
        assert fm["skills"] == ["distill", "session-brief"]
        # The commented-out `#model: fable` never shadows the live key.
        assert fm["model"] == "opus"
        assert fm["color"] == "purple"
        assert fm["permissionMode"] == "acceptEdits"
        assert fm["maxTurns"] == "25"
        assert fm["effort"] == "max"
        assert "You are echo." in body

    def test_no_front_matter_is_all_body(self):
        text = "Just a prompt body.\nNo fences here."
        fm, body = roles.parse_front_matter(text)
        assert fm == {}
        assert body == text

    def test_comment_inside_block_list_does_not_break_it(self):
        fm, _ = roles.parse_front_matter(
            "---\nskills:\n  - a\n#commented: out\n  - b\n---\n")
        assert fm["skills"] == ["a", "b"]

    def test_zero_indent_block_list_items_parse(self):
        # `tools:\n- Read` (zero-indent dash) is valid, common YAML that
        # PyYAML parses identically to the indented form — items must not be
        # silently dropped (that would widen a read-only role to ALL tools).
        fm, _ = roles.parse_front_matter(
            "---\nname: readonly\ntools:\n- Read\n- Bash\nskills:\n- distill\n  - session-brief\n---\nbody\n")
        assert fm["tools"] == ["Read", "Bash"]
        # Mixed indents in one list still collect in order.
        assert fm["skills"] == ["distill", "session-brief"]

    def test_stray_zero_indent_dash_without_open_list_is_ignored(self):
        # A dash line with NO open list key still falls through to the reset —
        # it must not invent a list or crash.
        fm, _ = roles.parse_front_matter(
            "---\n- orphan\nname: x\n---\n")
        assert fm == {"name": "x"}

    def test_unterminated_fence_consumes_to_eof(self):
        fm, body = roles.parse_front_matter("---\nname: x\n")
        assert fm["name"] == "x"
        assert body == ""

    def test_quoted_scalars_are_unquoted(self):
        # Real case: gsd-ui-researcher.md carries color: "#E879F9" — the quotes
        # protect the # from looking like a comment and must not survive parsing.
        fm, _ = roles.parse_front_matter(
            '---\ncolor: "#E879F9"\nname: \'quoted\'\ndescription: has "interior" quotes\n---\n')
        assert fm["color"] == "#E879F9"
        assert fm["name"] == "quoted"
        assert fm["description"] == 'has "interior" quotes'

    def test_quoted_hex_color_passes_through_to_color_hex(self, tmp_path):
        d = tmp_path / "agents"
        d.mkdir(parents=True)
        (d / "hexy.md").write_text('---\nname: hexy\ncolor: "#E879F9"\n---\nbody\n', encoding="utf-8")
        (out,) = roles.list_roles(d, "system")
        assert out["color"] == "#E879F9"
        assert out["color_hex"] == "#E879F9"


# ---------------------------------------------------------------------------
# Color mapping (named -> AG_COLORS hex; raw hex passthrough)
# ---------------------------------------------------------------------------

class TestColorMapping:
    def test_claude_named_colors_map_to_ag_hexes(self):
        assert roles.color_hex_for("purple") == _AG["violet"]
        assert roles.color_hex_for("red") == _AG["vermilion"]
        assert roles.color_hex_for("blue") == _AG["cobalt"]
        assert roles.color_hex_for("green") == _AG["emerald"]
        assert roles.color_hex_for("yellow") == _AG["citron"]
        assert roles.color_hex_for("orange") == _AG["amber"]
        assert roles.color_hex_for("pink") == _AG["magenta"]
        assert roles.color_hex_for("cyan") == _AG["cyan"]

    def test_ag_color_names_map_to_their_own_hex(self):
        assert roles.color_hex_for("teal") == _AG["teal"]
        assert roles.color_hex_for("Crimson") == _AG["crimson"]  # case-folded

    def test_raw_hex_passes_through(self):
        assert roles.color_hex_for("#a1B2c3") == "#a1B2c3"

    def test_unknown_or_missing_is_none(self):
        assert roles.color_hex_for("chartreuse-ish") is None
        assert roles.color_hex_for(None) is None
        assert roles.color_hex_for("") is None


# ---------------------------------------------------------------------------
# Listing (scope dirs -> LIGHT role payloads)
# ---------------------------------------------------------------------------

class TestListRoles:
    def test_full_payload_shape_light_no_body(self, tmp_path):
        d = tmp_path / "agents"
        _write(d, "echo.md", _FULL_MD)
        (out,) = roles.list_roles(d, "system")
        assert out["name"] == "echo"
        assert out["color"] == "purple"
        assert out["color_hex"] == _AG["violet"]
        # Wire keys are snake_case (sidecar API convention), values read from
        # the camelCase front-matter spellings.
        assert out["max_turns"] == 25                   # int, not "25"
        assert out["permission_mode"] == "acceptEdits"
        assert "maxTurns" not in out and "permissionMode" not in out
        assert out["scope"] == "system"
        assert Path(out["file"]).is_absolute()
        assert Path(out["file"]).name == "echo.md"
        # LIGHT: no body in the listing payload.
        assert "body" not in out
        assert not any("You are echo" in str(v) for v in out.values())

    def test_missing_name_falls_back_to_stem(self, tmp_path):
        d = tmp_path / "agents"
        _write(d, "vibe-guide.md", "---\ndescription: styles\n---\nbody\n")
        (out,) = roles.list_roles(d, "project")
        assert out["name"] == "vibe-guide"
        assert out["description"] == "styles"

    def test_no_front_matter_file_still_lists(self, tmp_path):
        d = tmp_path / "agents"
        _write(d, "bare.md", "Just a prompt, no fences.\n")
        (out,) = roles.list_roles(d, "system")
        assert out["name"] == "bare"
        assert out["description"] is None
        assert out["tools"] is None and out["skills"] is None

    def test_no_color_yields_null_pair(self, tmp_path):
        d = tmp_path / "agents"
        _write(d, "plain.md", "---\nname: plain\nmodel: inherit\n---\n")
        (out,) = roles.list_roles(d, "system")
        assert out["color"] is None and out["color_hex"] is None

    def test_hex_color_passthrough_in_listing(self, tmp_path):
        d = tmp_path / "agents"
        _write(d, "hexy.md", "---\nname: hexy\ncolor: #aa3a61\n---\n")
        (out,) = roles.list_roles(d, "system")
        assert out["color"] == "#aa3a61" and out["color_hex"] == "#aa3a61"

    def test_sorted_by_name_and_non_md_ignored(self, tmp_path):
        d = tmp_path / "agents"
        _write(d, "zeta.md", "---\nname: zeta\n---\n")
        _write(d, "alpha.md", "---\nname: alpha\n---\n")
        _write(d, "notes.txt", "not an agent")
        out = roles.list_roles(d, "system")
        assert [r["name"] for r in out] == ["alpha", "zeta"]

    def test_missing_dir_is_empty(self, tmp_path):
        assert roles.list_roles(tmp_path / "nope", "system") == []
        assert roles.list_roles(None, "project") == []


# ---------------------------------------------------------------------------
# Endpoint — GET /roles (two-scope shape + cwd-less degrade)
# ---------------------------------------------------------------------------

class TestRolesEndpoint:
    def test_two_scope_response_shape(self, tmp_path, monkeypatch):
        sys_dir = tmp_path / "sysagents"
        _write(sys_dir, "gsd-debugger.md",
               "---\nname: gsd-debugger\ncolor: orange\n"
               "tools: Read, Write, Edit\n---\nbody\n")
        monkeypatch.setenv("AWL_SYSTEM_AGENTS_DIR", str(sys_dir))

        proj = tmp_path / "proj"
        proj.mkdir()
        proj_agents = storage.agents_dir(str(proj))
        _write(proj_agents, "echo.md", _FULL_MD)

        out = asyncio.run(main.get_roles(cwd=str(proj)))

        # Group labels reproduce the mockup's ROLE_DEFS headers exactly.
        assert out["system"]["label"] == \
            "System agents (~/.claude/agents · cross-project)"
        assert out["project"]["label"] == \
            "Project agents (<project>/.awl-cc-dash/agents)"
        assert out["system"]["dir"] == str(sys_dir)
        assert out["project"]["dir"] == str(proj_agents)

        (sys_role,) = out["system"]["roles"]
        assert sys_role["name"] == "gsd-debugger"
        assert sys_role["scope"] == "system"
        assert sys_role["color_hex"] == _AG["amber"]   # orange -> amber

        (proj_role,) = out["project"]["roles"]
        assert proj_role["name"] == "echo"
        assert proj_role["scope"] == "project"
        assert proj_role["skills"] == ["distill", "session-brief"]

    def test_cwdless_degrades_to_null_project_scope(self, tmp_path, monkeypatch):
        sys_dir = tmp_path / "sysagents"
        _write(sys_dir, "a.md", "---\nname: a\n---\n")
        monkeypatch.setenv("AWL_SYSTEM_AGENTS_DIR", str(sys_dir))

        out = asyncio.run(main.get_roles(cwd=None))
        assert out["project"]["dir"] is None
        assert out["project"]["roles"] == []
        assert [r["name"] for r in out["system"]["roles"]] == ["a"]

    def test_empty_scopes_are_empty_lists_not_errors(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SYSTEM_AGENTS_DIR", str(tmp_path / "nothing"))
        proj = tmp_path / "proj2"
        proj.mkdir()
        out = asyncio.run(main.get_roles(cwd=str(proj)))
        assert out["system"]["roles"] == []
        assert out["project"]["roles"] == []   # dir named but not yet created
        assert out["project"]["dir"] is not None
