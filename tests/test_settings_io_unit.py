"""Hermetic unit tests for the sidecar's settings file I/O primitives.

Pure and path-explicit: every write targets a pytest ``tmp_path`` file, never the
real ``~/.claude`` or ``<project>/.claude``. The module under test hardcodes no
paths — it operates only on paths the caller passes in — so nothing here can
touch real user config. No driver, no tmux, no bridge.
"""

import sys
from pathlib import Path

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import json  # noqa: E402

import pytest  # noqa: E402

import settings_io  # noqa: E402


# ---------------------------------------------------------------------------
# read_json — tolerant of missing / empty / corrupt files
# ---------------------------------------------------------------------------

class TestReadJson:
    def test_missing_file_returns_empty(self, tmp_path):
        assert settings_io.read_json(tmp_path / "nope.json") == {}

    def test_empty_file_returns_empty(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text("", encoding="utf-8")
        assert settings_io.read_json(p) == {}

    def test_whitespace_only_returns_empty(self, tmp_path):
        p = tmp_path / "ws.json"
        p.write_text("   \n  ", encoding="utf-8")
        assert settings_io.read_json(p) == {}

    def test_corrupt_json_returns_empty(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{ this is not: json ]", encoding="utf-8")
        assert settings_io.read_json(p) == {}

    def test_non_object_json_returns_empty(self, tmp_path):
        # A valid JSON array/scalar is not a settings object -> {}.
        p = tmp_path / "arr.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        assert settings_io.read_json(p) == {}

    def test_valid_object_round_trips(self, tmp_path):
        p = tmp_path / "ok.json"
        p.write_text('{"a": 1, "b": {"c": 2}}', encoding="utf-8")
        assert settings_io.read_json(p) == {"a": 1, "b": {"c": 2}}

    def test_accepts_str_path(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text('{"x": true}', encoding="utf-8")
        assert settings_io.read_json(str(p)) == {"x": True}


# ---------------------------------------------------------------------------
# write_json — confirm-gated, atomic, pretty, creates parent dirs
# ---------------------------------------------------------------------------

class TestWriteJson:
    def test_without_confirm_raises_and_writes_nothing(self, tmp_path):
        p = tmp_path / "out.json"
        with pytest.raises(settings_io.ConfirmationRequired):
            settings_io.write_json(p, {"a": 1}, confirm=False)
        assert not p.exists()

    def test_confirm_false_raises_permissionerror_subclass(self, tmp_path):
        # ConfirmationRequired is a PermissionError so callers can catch either.
        p = tmp_path / "out.json"
        with pytest.raises(PermissionError):
            settings_io.write_json(p, {"a": 1}, confirm=False)

    def test_with_confirm_writes_and_round_trips(self, tmp_path):
        p = tmp_path / "out.json"
        data = {"a": 1, "nested": {"b": [1, 2, 3]}}
        returned = settings_io.write_json(p, data, confirm=True)
        assert returned == data
        assert p.exists()
        assert json.loads(p.read_text(encoding="utf-8")) == data

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "deep" / "nested" / "dir" / "settings.json"
        settings_io.write_json(p, {"ok": True}, confirm=True)
        assert p.exists()
        assert json.loads(p.read_text(encoding="utf-8")) == {"ok": True}

    def test_output_is_pretty_indented(self, tmp_path):
        p = tmp_path / "pretty.json"
        settings_io.write_json(p, {"a": {"b": 1}}, confirm=True)
        text = p.read_text(encoding="utf-8")
        assert "\n" in text and "  " in text  # multi-line, indented

    def test_overwrites_existing(self, tmp_path):
        p = tmp_path / "o.json"
        settings_io.write_json(p, {"v": 1}, confirm=True)
        settings_io.write_json(p, {"v": 2}, confirm=True)
        assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}

    def test_no_temp_files_left_behind(self, tmp_path):
        p = tmp_path / "clean.json"
        settings_io.write_json(p, {"a": 1}, confirm=True)
        leftovers = [f.name for f in tmp_path.iterdir() if f.name != "clean.json"]
        assert leftovers == []


# ---------------------------------------------------------------------------
# set_key — nested read-modify-write by dotted path
# ---------------------------------------------------------------------------

class TestSetKey:
    def test_creates_nested_path_and_persists(self, tmp_path):
        p = tmp_path / "s.json"
        doc = settings_io.set_key(p, "permissions.deny", ["Bash(rm)"], confirm=True)
        assert doc == {"permissions": {"deny": ["Bash(rm)"]}}
        assert json.loads(p.read_text(encoding="utf-8")) == doc

    def test_sets_scalar_on_existing_doc(self, tmp_path):
        p = tmp_path / "s.json"
        settings_io.write_json(p, {"env": {"FOO": "1"}}, confirm=True)
        doc = settings_io.set_key(p, "env.BAR", "2", confirm=True)
        assert doc == {"env": {"FOO": "1", "BAR": "2"}}

    def test_top_level_key(self, tmp_path):
        p = tmp_path / "s.json"
        doc = settings_io.set_key(p, "model", "opus", confirm=True)
        assert doc == {"model": "opus"}

    def test_overwrites_intermediate_scalar_with_dict(self, tmp_path):
        # A scalar sitting where a dict must go is replaced by the container.
        p = tmp_path / "s.json"
        settings_io.write_json(p, {"a": 5}, confirm=True)
        doc = settings_io.set_key(p, "a.b", 1, confirm=True)
        assert doc == {"a": {"b": 1}}

    def test_without_confirm_raises_and_no_write(self, tmp_path):
        p = tmp_path / "s.json"
        with pytest.raises(settings_io.ConfirmationRequired):
            settings_io.set_key(p, "a.b", 1, confirm=False)
        assert not p.exists()


# ---------------------------------------------------------------------------
# toggle_key — flip a boolean at a dotted path (absent == False)
# ---------------------------------------------------------------------------

class TestToggleKey:
    def test_absent_becomes_true_then_false(self, tmp_path):
        p = tmp_path / "t.json"
        d1 = settings_io.toggle_key(p, "flags.enabled", confirm=True)
        assert d1 == {"flags": {"enabled": True}}
        d2 = settings_io.toggle_key(p, "flags.enabled", confirm=True)
        assert d2 == {"flags": {"enabled": False}}
        d3 = settings_io.toggle_key(p, "flags.enabled", confirm=True)
        assert d3 == {"flags": {"enabled": True}}
        assert json.loads(p.read_text(encoding="utf-8")) == {"flags": {"enabled": True}}

    def test_existing_true_toggles_false(self, tmp_path):
        p = tmp_path / "t.json"
        settings_io.write_json(p, {"on": True}, confirm=True)
        assert settings_io.toggle_key(p, "on", confirm=True) == {"on": False}

    def test_non_bool_existing_value_is_coerced_by_truthiness(self, tmp_path):
        # A non-boolean present value flips based on its truthiness.
        p = tmp_path / "t.json"
        settings_io.write_json(p, {"x": "yes"}, confirm=True)
        assert settings_io.toggle_key(p, "x", confirm=True) == {"x": False}

    def test_without_confirm_raises(self, tmp_path):
        p = tmp_path / "t.json"
        with pytest.raises(settings_io.ConfirmationRequired):
            settings_io.toggle_key(p, "a", confirm=False)
        assert not p.exists()


# ---------------------------------------------------------------------------
# remove_key — delete a nested key if present
# ---------------------------------------------------------------------------

class TestRemoveKey:
    def test_deletes_present_nested_key(self, tmp_path):
        p = tmp_path / "r.json"
        settings_io.write_json(p, {"a": {"b": 1, "c": 2}}, confirm=True)
        doc = settings_io.remove_key(p, "a.b", confirm=True)
        assert doc == {"a": {"c": 2}}
        assert json.loads(p.read_text(encoding="utf-8")) == {"a": {"c": 2}}

    def test_deletes_top_level_key(self, tmp_path):
        p = tmp_path / "r.json"
        settings_io.write_json(p, {"a": 1, "b": 2}, confirm=True)
        assert settings_io.remove_key(p, "a", confirm=True) == {"b": 2}

    def test_absent_key_is_noop_and_persists(self, tmp_path):
        p = tmp_path / "r.json"
        settings_io.write_json(p, {"a": 1}, confirm=True)
        assert settings_io.remove_key(p, "x.y.z", confirm=True) == {"a": 1}
        assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}

    def test_absent_on_missing_file_is_empty(self, tmp_path):
        p = tmp_path / "nope.json"
        assert settings_io.remove_key(p, "a.b", confirm=True) == {}

    def test_without_confirm_raises(self, tmp_path):
        p = tmp_path / "r.json"
        settings_io.write_json(p, {"a": 1}, confirm=True)
        with pytest.raises(settings_io.ConfirmationRequired):
            settings_io.remove_key(p, "a", confirm=False)
        # Untouched by the failed write.
        assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}


# ---------------------------------------------------------------------------
# account_band — read-only creds mapping (email/org/plan), lenient field names
# ---------------------------------------------------------------------------

class TestAccountBand:
    def test_maps_canonical_fields(self, tmp_path):
        p = tmp_path / "creds.json"
        p.write_text(json.dumps({
            "email": "a@b.com", "org": "Acme", "plan": "max",
        }), encoding="utf-8")
        assert settings_io.account_band(p) == {
            "email": "a@b.com", "org": "Acme", "plan": "max"}

    def test_maps_alternate_field_names(self, tmp_path):
        p = tmp_path / "creds.json"
        p.write_text(json.dumps({
            "emailAddress": "c@d.com",
            "organization": "Globex",
            "subscriptionType": "pro",
        }), encoding="utf-8")
        assert settings_io.account_band(p) == {
            "email": "c@d.com", "org": "Globex", "plan": "pro"}

    def test_partial_fields_present(self, tmp_path):
        p = tmp_path / "creds.json"
        p.write_text(json.dumps({"email": "e@f.com"}), encoding="utf-8")
        band = settings_io.account_band(p)
        assert band["email"] == "e@f.com"
        assert band.get("org") is None
        assert band.get("plan") is None
        assert "signed_out" not in band

    def test_nested_account_object(self, tmp_path):
        # Real creds often nest under an "account"/"oauthAccount" object.
        p = tmp_path / "creds.json"
        p.write_text(json.dumps({
            "oauthAccount": {"emailAddress": "n@o.com",
                             "organizationName": "Nest Inc",
                             "planType": "team"}
        }), encoding="utf-8")
        assert settings_io.account_band(p) == {
            "email": "n@o.com", "org": "Nest Inc", "plan": "team"}

    def test_missing_file_is_signed_out(self, tmp_path):
        assert settings_io.account_band(tmp_path / "nope.json") == {"signed_out": True}

    def test_no_recognized_fields_is_signed_out(self, tmp_path):
        p = tmp_path / "creds.json"
        p.write_text(json.dumps({"unrelated": 1}), encoding="utf-8")
        assert settings_io.account_band(p) == {"signed_out": True}

    def test_corrupt_creds_is_signed_out(self, tmp_path):
        p = tmp_path / "creds.json"
        p.write_text("{ broken", encoding="utf-8")
        assert settings_io.account_band(p) == {"signed_out": True}

    def test_claude_json_tier_fields_are_not_plan(self, tmp_path):
        # The §11 #33 boundary, single-file side: `.claude.json`'s tier-ish
        # oauthAccount fields (organizationType/seatTier/organizationRateLimitTier/
        # billingType) are NOT surfaced as "plan" by the single-file reader —
        # the plan label comes only from the credentials file (split source).
        p = tmp_path / "claude.json"
        p.write_text(json.dumps({
            "oauthAccount": {
                "emailAddress": "a@b.com",
                "organizationName": "Acme",
                "organizationType": "claude_max",
                "seatTier": None,
                "organizationRateLimitTier": "default_claude_max_5x",
                "billingType": "stripe_subscription",
            }
        }), encoding="utf-8")
        band = settings_io.account_band(p)
        assert band == {"email": "a@b.com", "org": "Acme"}
        assert "plan" not in band


# ---------------------------------------------------------------------------
# account_band_split — the §11 #33 split-source reader (live-mapped boundary:
# email/org from .claude.json oauthAccount; plan ONLY from .credentials.json
# claudeAiOauth.subscriptionType; + rate_limit_tier and the read-only
# auth_expiry signal, null when the creds expose no expiry)
# ---------------------------------------------------------------------------

def _write_claude_json(tmp_path, **overrides):
    """A realistic .claude.json mirror (the real oauthAccount shape)."""
    oauth = {
        "emailAddress": "adam@example.com",
        "organizationName": "adam@example.com's Organization",
        "organizationType": "claude_max",
        "organizationRateLimitTier": "default_claude_max_5x",
        "billingType": "stripe_subscription",
        "seatTier": None,
    }
    oauth.update(overrides)
    p = tmp_path / "claude.json"
    p.write_text(json.dumps({"oauthAccount": oauth}), encoding="utf-8")
    return p


def _write_credentials(tmp_path, *, expires_at=1784106632120, **overrides):
    """A realistic .credentials.json mirror (the real claudeAiOauth shape,
    token values elided)."""
    oauth = {
        "accessToken": "sk-elided",
        "refreshToken": "sk-elided",
        "subscriptionType": "max",
        "rateLimitTier": "default_claude_max_20x",
        "scopes": ["user:inference"],
    }
    if expires_at is not None:
        oauth["expiresAt"] = expires_at
    oauth.update(overrides)
    p = tmp_path / "credentials.json"
    p.write_text(json.dumps({"claudeAiOauth": oauth}), encoding="utf-8")
    return p


class TestAccountBandSplit:
    def test_merges_email_org_from_claude_json_and_plan_from_creds(self, tmp_path):
        cj = _write_claude_json(tmp_path)
        cr = _write_credentials(tmp_path)
        band = settings_io.account_band_split(cj, cr)
        assert band["email"] == "adam@example.com"
        assert band["org"] == "adam@example.com's Organization"
        assert band["plan"] == "max"                     # creds, not org-type
        assert band["rate_limit_tier"] == "default_claude_max_20x"
        # epoch ms 1784106632120 == 2026-07-15T09:10:32Z
        assert band["auth_expiry"] == "2026-07-15T09:10:32Z"

    def test_creds_plan_wins_over_claude_json_org_type(self, tmp_path):
        cj = _write_claude_json(tmp_path, organizationType="claude_enterprise")
        cr = _write_credentials(tmp_path)
        assert settings_io.account_band_split(cj, cr)["plan"] == "max"

    def test_missing_creds_falls_back_to_org_type_honestly(self, tmp_path):
        cj = _write_claude_json(tmp_path)
        band = settings_io.account_band_split(cj, tmp_path / "nope.json")
        assert band["email"] == "adam@example.com"
        # The raw recorded value — never a synthesized label.
        assert band["plan"] == "claude_max"
        assert band["rate_limit_tier"] == "default_claude_max_5x"
        assert band["auth_expiry"] is None

    def test_missing_claude_json_still_yields_plan_and_expiry(self, tmp_path):
        cr = _write_credentials(tmp_path)
        band = settings_io.account_band_split(tmp_path / "nope.json", cr)
        assert "email" not in band
        assert band["plan"] == "max"
        assert band["auth_expiry"] == "2026-07-15T09:10:32Z"

    def test_absent_expiry_is_null_but_key_present(self, tmp_path):
        cj = _write_claude_json(tmp_path)
        cr = _write_credentials(tmp_path, expires_at=None)
        band = settings_io.account_band_split(cj, cr)
        assert "auth_expiry" in band and band["auth_expiry"] is None

    def test_zero_or_bogus_expiry_is_null(self, tmp_path):
        # A logged-out creds file zeroes expiresAt — null, not 1970.
        cj = _write_claude_json(tmp_path)
        cr = _write_credentials(tmp_path, expires_at=0)
        assert settings_io.account_band_split(cj, cr)["auth_expiry"] is None
        cr2 = tmp_path / "c2.json"
        cr2.write_text(json.dumps(
            {"claudeAiOauth": {"subscriptionType": "max",
                               "expiresAt": "not-a-number"}}), encoding="utf-8")
        assert settings_io.account_band_split(cj, cr2)["auth_expiry"] is None

    def test_seconds_epoch_also_parses(self, tmp_path):
        cj = _write_claude_json(tmp_path)
        cr = _write_credentials(tmp_path, expires_at=1784106632)  # seconds
        band = settings_io.account_band_split(cj, cr)
        assert band["auth_expiry"] == "2026-07-15T09:10:32Z"

    def test_both_missing_is_signed_out(self, tmp_path):
        out = settings_io.account_band_split(
            tmp_path / "a.json", tmp_path / "b.json")
        assert out == {"signed_out": True}

    def test_no_tier_info_anywhere_omits_plan_and_tier(self, tmp_path):
        cj = tmp_path / "claude.json"
        cj.write_text(json.dumps({"oauthAccount": {
            "emailAddress": "x@y.com", "organizationName": "XY"}}),
            encoding="utf-8")
        band = settings_io.account_band_split(cj, tmp_path / "nope.json")
        assert band["email"] == "x@y.com"
        assert "plan" not in band and "rate_limit_tier" not in band
        assert band["auth_expiry"] is None
