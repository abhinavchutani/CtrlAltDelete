# Running our agents together (human guide)

Each of us runs one AI agent on our own laptop. The agents never talk directly; they coordinate through GitHub:

| Channel | What it's for |
|---|---|
| 🤖 **Agent chat**, the pinned issue | A shared group chat. Each agent reads the latest messages and posts one status per run |
| **`agent-task` issues** | The task board. Agents *claim* a task (label + comment) so two agents never build the same thing |
| **PRs** | Every change goes through a PR that a *different* agent (or a human) reviews before merging |
| **`needs-human`** label | Anything that needs a human decision. Check these first thing in the morning |

The rules the agents follow are in [`AGENTS.md`](../AGENTS.md). The per-run routine is [`AGENT_LOOP.md`](AGENT_LOOP.md).

## One-time setup (each person)

1. **Repo access.** Abhinav adds you as a collaborator on GitHub.
2. **Clone and set up:**
   ```bash
   git clone https://github.com/abhinavchutani/CtrlAltDelete.git && cd CtrlAltDelete
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   cp .env.example .env    # set AGENT_NAME, e.g. sara-claude (unique per person!)
   unzip ~/Downloads/Apetit_SinceAI2026/APETIT_CLIMATE_NATURE_NAVIGATOR_2026.zip -d data/
   ```
3. **GitHub CLI.** Run `gh auth login` and check it with `gh auth status`. The agent acts with **your** GitHub account. Approvals only work between *different* accounts, so each person's agent must run under their own account.
4. **Check the helper:**
   ```bash
   scripts/agent-chat.sh whoami
   scripts/agent-chat.sh read 5
   scripts/agent-chat.sh tasks
   ```

## Starting your agent for the night

**Claude Code** (CLI or desktop app), opened in the repo folder:

```
/loop 30m Follow docs/AGENT_LOOP.md exactly.
```

**Codex, Cursor or another agent:** paste the contents of `docs/AGENT_LOOP.md` as the instruction and have it re-run every ~30 minutes. Use the tool's own scheduling or loop feature, or re-run it in a shell loop.

**Before you sleep:**
- Laptop on power and kept awake: on macOS, run `caffeinate -dims` in a terminal.
- Your agent is allowed to edit files and run `git`, `gh`, `python` and `pytest` without asking. Otherwise it stalls on the first permission prompt.
- Your agent is **not** allowed to run destructive commands. Keep your tool's safety settings on.
- You've left it a lane if you want (`AGENT_LANE=C` in `.env`) so the agents split the work.

## In the morning

1. Read the 🤖 Agent chat from the bottom up.
2. Handle every `needs-human` issue and PR.
3. Merge the approved PRs the agents left for humans (protected paths, `submissions/`).
4. Re-prioritise the task board. Close or rewrite tasks that went sideways.

## Notes and limits

- **No hard protection on `main`.** The repo is private on a free plan, so GitHub branch protection isn't available. "Never push to main" is a rule the agents follow, not a lock.
- **Claims are best-effort.** If two agents claim the same task within seconds, the first claim comment wins and the other backs off automatically.
- **Keep it cheap and quiet:** one status message per run, small PRs, no data in issues.
- **Labels in use:**
  - `agent-chat`, `agent-task`
  - `status:todo`, `status:claimed`, `status:in-review`
  - `needs-human`, `decision`
  - `track:A`, `track:C`, `track:E`, `track:app`, `track:docs`
