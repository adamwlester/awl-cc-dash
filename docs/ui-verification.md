# UI verification

How to verify a user interface (UI) change before calling it done. The tool is the repo's own `ui-verify` launcher; its setup, command line and scripting interface are in [dev/tools/ui-verify/README.md](../dev/tools/ui-verify/README.md).

## Drive the rendered UI

For anything that renders (the dashboard mockups above all), `node --check`, grep or reading the diff is necessary but not sufficient: it says nothing about layout, wrapping, overflow, or whether a control actually works. Layout, formatting, overflow and dynamic behavior are part of the deliverable, not the user's job to catch.

## One headed pass, parked

- Drive the change through `dev/tools/ui-verify/`. It serves over `localhost` and runs a real headed Chromium parked behind the user's windows, so it never steals focus; run it freely, even while he is active.
- Every pass is already headed, so there is no headless-versus-headed rendering gap to reconcile. Do not add a separate "headed parity" re-screenshot pass (the retired workflow iterated headless, then re-shot once headed; that second pass caught only mode drift, which no longer exists).
- "One pass" drops the mode-reconciliation pass only; it does not mean checking fewer states or controls.

## In that pass, before you call it done

- Resize the affected panels to both narrow and wide extremes: the layout is resizable, and that is where it breaks.
- Click through every control you touched: expand and collapse, toggles, each dropdown and menu, the whole flow.
- Screenshot each state into `.scratch/ui-verify/`, compare it to the stated intent, and fix what is off, all before reporting back.

This width scrutiny and click coverage is the real quality gate, not the browser mode: earlier layout misses came from thin screenshot scrutiny, not from which mode was used.

For variant work, also run `node dev/tools/variant-lint/variant-lint.mjs` (see [design-changes.md](design-changes.md)).
