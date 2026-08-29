# Agent Instructions

- Before starting a change, run `scripts/agent/pre_final_check.sh`. If the
  worktree is dirty, stop and inventory the existing work before adding more.
- For each change, create a commit before the final response.
- Install the repository hooks with `scripts/agent/install_git_hooks.sh`. The
  pre-commit hook rejects partial commits that leave unstaged or untracked
  files behind.
- If verification fails, do not commit unless the user explicitly asks for a
  failed or diagnostic checkpoint commit.
- Final responses for code/doc changes must include the commit hash, or explain
  why no commit was made.
- Before the final response, run `scripts/agent/pre_final_check.sh` when it
  exists. A nonzero exit means there is uncommitted work that must be committed
  or explicitly explained.
