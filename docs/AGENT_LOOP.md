# Agent loop: run this every time you wake up

You are agent `$AGENT_NAME` (from `.env`) on team CtrlAltDelete. Follow `AGENTS.md`. Work in this order, and stop when this run's work is done.

1. **Sync.**
   ```bash
   git fetch origin --prune
   git -C . switch main && git pull --ff-only
   ```
   If you have an active worktree in `.worktrees/<issue>`, rebase it on `origin/main`.

2. **Read the chat.**
   ```bash
   scripts/agent-chat.sh read 30
   ```
   Answer questions addressed to `@agent:$AGENT_NAME` or `@agent:all` with one `say`.

3. **Review.**
   ```bash
   scripts/agent-chat.sh reviews
   ```
   For each PR you did not write: check out the branch, run `pytest -q` and its reproduce command, read the diff, check it against the domain guardrails in AGENTS.md section 8, then approve or request changes. If a PR you approved is mergeable under the merge rule, squash-merge it.

4. **Work.**
   - If `scripts/agent-chat.sh mine` shows a claimed task, continue it.
   - Otherwise run `scripts/agent-chat.sh tasks`, pick the highest-priority unclaimed task (in your `AGENT_LANE` if set), and `claim` it.
   - **No tasks?** Don't invent scope. Post `IDLE` once, then stop.
   - Work in your worktree and branch. Commit small. Push.
   - When it's ready, open or update the PR (`Closes #<n>`, template filled) and label it `status:in-review`:
     ```bash
     gh pr edit <pr> --add-label status:in-review
     ```

5. **Report.** Post exactly one message:
   ```bash
   scripts/agent-chat.sh say "STATUS: done … | next … | blockers …"
   ```

6. **Stop conditions:**
   - **A scope or product decision is needed:** run `block <n> "question"` and move on.
   - **Your human's limits are reached** (time, budget, permissions): post a `HANDOFF` and `release` your task.
   - **You're about to do anything listed under Safety in AGENTS.md:** don't.
