# Prompt library — shipped defaults: Compose snippets & canned templates (§11 #45)

The Compose snippet/template canned texts (§7.14), in the `## group` / `### item` convention (`sidecar/prompt_library.py`). `{placeholder}` tokens are the fill-in pills of the Compose editor's template blocks. Seeded verbatim from the current design mockup's canned template set (`design/behavior.js` `TEMPLATES` — including the reviewer-request send text, "Code review request"); the Compose-side consumers are design-lane work queued under §11 #45/#37. The backend `templates_store` (user-*saved* templates, `sidecar/runtime/templates.json`) is a separate store by design (§7.14) — these are the shipped canned texts, not user data. A project copy at `<project>/.awl-cc-dash/docs/prompts/snippets.md` overrides item-by-item.

## compose-snippets

### Security audit request

Run a focused security audit of {target_module}. Flag anything at or above {severity_threshold} severity, with a concrete exploit path for each finding. Post results to {destination} grouped by severity, and notify {notify_agent} when the {format} summary is ready.

### Code review request

Review the diff on {branch} for {focus}. Call out blocking issues first, then nits, and confirm the {test_scope} tests cover the change before approving.

### Refactor proposal

Propose a refactor of {module} to improve {goal}. Keep behavior identical, lay the steps out as a checklist, and flag any risky {risk_area} touchpoints.

### Bug triage & severity

Triage {issue}: reproduce it, assign a severity ({severity}), identify the root cause, and suggest an owner. Post the writeup to {destination}.
