# Agent Instructions

- For each change, create a commit before the final response.
- If verification fails, do not commit unless the user explicitly asks for a
  failed or diagnostic checkpoint commit.
- Final responses for code/doc changes must include the commit hash, or explain
  why no commit was made.
- Before the final response, run `scripts/agent/pre_final_check.sh` when it
  exists. A nonzero exit means there is uncommitted work that must be committed
  or explicitly explained.
