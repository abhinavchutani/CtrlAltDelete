# Agent loop: run this every time you wake up

You are agent `$AGENT_NAME` (from `.env`) on team CtrlAltDelete. Your focus area is `$AGENT_LANE`. Follow `AGENTS.md`. Work in this order.

**Context lives on GitHub, not in your memory.** The chat, your task issue's comments and the PRs are the shared record. Read them every run, even if you think you remember.

1. **Sync the main checkout** (never edit files here):
   ```bash
   git fetch origin --prune && git switch main && git pull --ff-only
   ```

2. **Read the chat:**
   ```bash
   scripts/agent-chat.sh read 30
   ```
   - Answer anything addressed to `@agent:$AGENT_NAME` or `@agent:all`.
   - If someone asks for help you can give quickly (an interface, a file location, a review), give it.
   - Note who is doing what, so you don't duplicate work.

3. **Review first:**
   ```bash
   scripts/agent-chat.sh reviews
   ```
   For each PR you did not write:
   1. Check it out: `gh pr checkout <n>` inside a scratch worktree, or read `gh pr diff <n>`.
   2. Run `pytest -q` and the PR's reproduce command.
   3. Check it against AGENTS.md section 8.
   4. Approve or request changes: `gh pr review <n> --approve|--request-changes -b "[$AGENT_NAME] …"`.
   5. If it now meets the merge rule (CI green, approved by someone else, no `needs-human`, no protected paths), squash-merge it: `gh pr merge <n> --squash --delete-branch`. Then post a `HANDOFF` saying what landed.

4. **Work:**
   - **If `scripts/agent-chat.sh mine` shows a task:** `cd .worktrees/<n>`, read the issue and its comments (`gh issue view <n> --comments`), run `git fetch origin && git merge --no-edit origin/main`, and continue.
   - **Otherwise:** run `scripts/agent-chat.sh tasks` and pick by AGENTS.md section 4 (lane → priority → dependencies closed). Then:
     ```bash
     scripts/agent-chat.sh claim <n>
     scripts/agent-chat.sh start <n> <slug>
     cd .worktrees/<n>
     ```
   - **Build in that worktree:**
     - Activate the environment with `source .venv/bin/activate`.
     - Commit small (`[$AGENT_NAME] …`) and `git push -u origin HEAD`.
     - Open a draft PR early: `gh pr create --draft --title "[$AGENT_NAME] #<n> …" --body "Closes #<n> …"`. That lets others see your progress.
   - **When the PR is ready** (done-when met, tests pass, scores and evidence in the PR body): run `gh pr ready <pr>`, then `gh pr edit <pr> --add-label status:in-review`, and post a `REVIEW` request in the chat.
   - **If you need an interface from another task,** agree it in the chat (file name, columns, function signature) and write it into both issues. Don't wait silently.
   - **Nothing claimable** (all tasks claimed or blocked)? Then:
     - review again;
     - write tests for merged code;
     - improve docs;
     - or propose up to 2 well-scoped new tasks with `new-task`. Only within the decided scope in issue #2: no new features nobody asked for.

     If there's truly nothing, post `IDLE` once.

5. **Leave a progress note** on your task issue:
   ```bash
   gh issue comment <n> --body "[$AGENT_NAME] progress: done … / next … / notes …"
   ```

6. **Post one status line to the chat:**
   ```bash
   scripts/agent-chat.sh say "STATUS: #<n> done … | next … | blockers …"
   ```

**Stop conditions:**
- **A product or scope decision is needed:** run `block <n> "question"` and move to other work.
- **You hit your limits** (time, usage, permissions): post a `HANDOFF` and `release` your task.
- **Anything in AGENTS.md section 9 (Safety) applies:** don't.
