"""Hermetic tests for the utility-LLM pass helpers (`sidecar/utility_llm.py`).
Pure parts only — the actual one-shot SDK call is exercised live (needs auth)."""
import sys
from pathlib import Path

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import utility_llm  # noqa: E402


def test_revise_scope_selects_system():
    assert "copy-editor" in utility_llm.revise_system("grammar").lower()
    assert "clarity" in utility_llm.revise_system("language").lower()
    assert "restructure" in utility_llm.revise_system("refactor").lower()


def test_revise_defaults_to_grammar():
    assert utility_llm.revise_system(None) == utility_llm.REVISE_SYSTEMS["grammar"]
    assert utility_llm.revise_system("unknown-scope") == utility_llm.REVISE_SYSTEMS["grammar"]


class _Block:
    def __init__(self, text):
        self.text = text


class _Msg:
    def __init__(self, content):
        self.content = content


def test_text_of_extracts_blocks():
    m = _Msg([_Block("hello "), _Block("world")])
    assert utility_llm._text_of(m) == ["hello ", "world"]


def test_text_of_handles_str_content():
    assert utility_llm._text_of(_Msg("plain")) == ["plain"]


def test_text_of_handles_dict_blocks():
    assert utility_llm._text_of(_Msg([{"type": "text", "text": "hi"}])) == ["hi"]


def test_text_of_empty():
    assert utility_llm._text_of(_Msg(None)) == []
