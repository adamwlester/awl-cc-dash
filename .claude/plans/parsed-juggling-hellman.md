# Un-commit two WIP docs from the last (already-pushed) commit

## Context

The last commit — `4e306f7 "Minor change to sizing tokens."` — was meant to carry only `design/tokens.css`, but it accidentally also swept in two work-in-progress dev-notes files that are still being edited: `dev/notes/TODO.md` and `dev/notes/scratch/2026-07-03-doc-integration-tracker.md`. The commit is already pushed (`main` and `origin/main` are in sync), so the clean fix rewrites that one commit to contain only `tokens.css` and force-pushes the corrected version. Goal: keep the intended `tokens.css` change committed, drop the two docs back to uncommitted WIP on disk (content untouched), and leave history showing a single tokens-only commit.

This is a solo personal repo, so the force-push is low-risk; `--force-with-lease` is used so it aborts if the remote unexpectedly moved.

## Steps

1. `git reset --soft HEAD~1` — undo `4e306f7`, keeping all three files' changes staged and the working tree untouched (the *safe* reset — never `--hard`).
2. `git restore --staged dev/notes/TODO.md "dev/notes/scratch/2026-07-03-doc-integration-tracker.md"` — un-stage the two docs. Their on-disk content is untouched; they return to being uncommitted WIP (TODO.md as modified, the tracker as untracked).
3. `git commit -m "Minor change to sizing tokens."` — re-create the commit with only `design/tokens.css`.
4. `git push --force-with-lease` — replace the previously-pushed commit on `origin/main`.

## Verification

- `git show --stat HEAD` → the new commit lists **only** `design/tokens.css`.
- `git status -sb` → `main` in sync with `origin/main`; the two docs appear as uncommitted changes (modified / untracked), confirming their WIP content is preserved on disk.
- `git log --oneline -3` → history reads cleanly with the tokens-only commit on top.

## Note

Doing nothing is also fine — the two files are just dev notes, and a WIP snapshot in history is harmless. This plan only applies if you'd rather they not be in the pushed commit. (Separately: the Summarize split-button design is still mid-discussion — six options in Digest/Extract groups agreed; only the color tier is open — and will get its own plan once that's settled.)
