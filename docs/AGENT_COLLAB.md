# Running our agents together (human guide)

Each of us runs one Claude Code agent on our own laptop. The agents never talk directly; they coordinate through GitHub:

| Channel | What it's for |
|---|---|
| 🤖 **Agent chat** (issue #1, pinned) | A shared group chat. Agents read the last 30 messages every run and post a status |
| **`agent-task` issues** | The task board. Agents *claim* a task (label + comment) so two never build the same thing. Each task lists its lane, priority and dependencies |
| **Task issue comments** | Each agent leaves a progress note every run. That's the hand-over memory |
| **PRs** | Every change. A *different* agent (or a human) reviews before merging |
| **`needs-human`** label | Decisions for us in the morning |

The rules are in [`AGENTS.md`](../AGENTS.md), the per-run routine is [`AGENT_LOOP.md`](AGENT_LOOP.md), and the interfaces between lanes are in [`CONTRACTS.md`](CONTRACTS.md).

## Lanes (one per person, from SYSTEM_DESIGN.md)

Each agent gets a focus area through `AGENT_LANE` in its `.env`: `A` (Data), `C` (Climate) or `platform` (schema, app, copilot, story).

| Person | `AGENT_NAME` | `AGENT_LANE` |
|---|---|---|
| Person 1 · Data | `<name>-claude` | `A` |
| Person 2 · Climate | `<name>-claude` | `C` |
| Person 3 · Platform + story | `<name>-claude` | `platform` |

Lanes are preferences, not walls. An agent with nothing unblocked in its lane helps elsewhere.

## One-time setup (each person, ~10 min)

```bash
git clone https://github.com/abhinavchutani/CtrlAltDelete.git && cd CtrlAltDelete
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
unzip ~/Downloads/Apetit_SinceAI2026/APETIT_CLIMATE_NATURE_NAVIGATOR_2026.zip -d data/
cp .env.example .env      # set AGENT_NAME (unique!) and AGENT_LANE
mkdir -p .claude && cp docs/claude-settings.recommended.json .claude/settings.json
gh auth login             # your own GitHub account
scripts/agent-chat.sh whoami && scripts/agent-chat.sh tasks
```

- **`.claude/settings.json`** pre-approves git, gh, python, pip, pytest, npm and file edits, so your agent doesn't stall on permission prompts at 3 a.m. It also **blocks** force-push, pushing to `main`, `rm -rf`, `git reset --hard`, `git clean` and deleting issues or repos.
- **Use your own GitHub account.** GitHub won't let an account approve its own PR, so reviews only work across people.
- **For the copilot,** put an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env` if you have one. Without a key, the copilot task builds an offline stub and flags `needs-human`.

## Before you sleep

1. Plug in your laptop and keep it awake: run `caffeinate -dims` in a terminal tab and leave it running.
2. Open Claude Code in the repo folder. In the desktop app, choose the CtrlAltDelete folder and set the permission mode to **Auto** if it's offered, otherwise **Accept edits**.
3. Start the loop with the prompt the team agrees on. The routine every run follows is [`AGENT_LOOP.md`](AGENT_LOOP.md). Agents only build `agent-task` issues, so nothing happens until tasks exist on the board.

## In the morning

1. Read 🤖 Agent chat (#1) from the bottom up.
2. Handle `needs-human` issues and PRs.
3. Merge approved PRs that touch protected paths.
4. Re-prioritise the board.

## Notes and limits

- **No hard protection on `main`.** Branch protection isn't available on a free private repo; the deny rules in `.claude/settings.json` plus `AGENTS.md` are the guardrails.
- **Claims are best-effort.** The first claim comment wins, and the other agent backs off automatically.
- **Usage limits:** a long night of work can hit Claude plan limits. The agent then stops until the limit resets, and the loop resumes after.
- **Labels:**
  - `agent-chat`, `agent-task`
  - `status:todo`, `status:claimed`, `status:in-review`
  - `needs-human`, `decision`
  - `track:A`, `track:C`, `track:E`, `track:app`, `track:docs`
