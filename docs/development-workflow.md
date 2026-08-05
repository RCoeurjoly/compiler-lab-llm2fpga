# Development workflow

Every repository change must be committed before moving on to the next change. Use a focused commit message that describes the completed change, and keep generated build outputs, Nix result symlinks, caches, and temporary diagnostic directories out of commits unless they are explicitly requested as durable artifacts.

Before finishing a task, run `git status`, review the staged diff, run the relevant tests, and leave the worktree clean except for deliberate user changes. If unrelated user changes are already present, preserve them and do not include them in the task commit.
