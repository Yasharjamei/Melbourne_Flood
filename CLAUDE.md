# Working rules for AI assistants in this repository

The owner set these rules; they apply to every session.

## Git
- **Work in a git worktree, never directly in the main checkout.** Follow CONTRIBUTING.md §5.
  1. `git worktree add -b wt/<topic> ../mf-<topic> origin/main`, then link `data/raw` into it.
  2. Commit there.
  3. `git push origin HEAD:main`.
  4. Remove the worktree and delete the local `wt/` branch.
- **GitHub has one branch, `main`.** Never push any other branch, never open a pull request, and never force-push `main`.
- **Commits are authored and committed by the owner:** `Yashar <yashar.jamei@gmail.com>`. Set it in the repository's local git config if it isn't. Do not add `Co-Authored-By`, `Claude-Session` or any other assistant trailer or footer to commit messages.
- Do not name the development environment's branch or the reference map's city in commits or files.

## Docs travel with code
Follow CONTRIBUTING.md §4.
- A user-visible change adds a line to `CHANGELOG.md`.
- A method change updates the README's Method section.
- A decision goes in `docs/PROJECT_LOG.md`.
- A change to how the code fits together updates `docs/ARCHITECTURE.md`.
