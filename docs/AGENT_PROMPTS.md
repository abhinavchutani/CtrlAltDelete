# Overnight agent prompts (copy-paste)

## Before you start (each person, once)

```bash
cd CtrlAltDelete && git pull
[ -d .venv ] || python3 -m venv .venv      # first time on this laptop
source .venv/bin/activate && pip install -r requirements.txt
mkdir -p .claude && cp docs/claude-settings.recommended.json .claude/settings.json
```

Then do the following:

1. **Set your `.env`:** a unique `AGENT_NAME` (e.g. `ashutosh-claude`) and your `AGENT_LANE` (`A`, `C` or `platform`).
2. **Check the setup:** run `scripts/agent-chat.sh whoami`; it must print your name, lane and GitHub user.
3. **Turn on auto-continue at usage limits.** This is a user setting; the project file may not be enough:
   ```bash
   python3 -c "import json,os;p=os.path.expanduser('~/.claude/settings.json');d=json.load(open(p)) if os.path.exists(p) else {};d['autoContinueAtUsageLimit']=True;json.dump(d,open(p,'w'),indent=2)"
   ```
4. **Keep the Mac awake:** plug it in, keep the lid open, and run `caffeinate -dims` in a terminal tab.
5. **Open a fresh Claude Code session** with the CtrlAltDelete folder:
   - **Model:** Opus 5.5
   - **Effort:** High
   - **Permission mode:** Auto (or Accept edits)

## The prompt (paste once; `/loop` re-runs it every 15 minutes)

Pick the block for your lane.

### Lane A (Person 1 · Data)

```
/loop 15m You are the CtrlAltDelete Data agent (AGENT_LANE=A), working overnight while your human sleeps. On your first run in this session, read AGENTS.md, docs/SYSTEM_DESIGN.md, docs/CONTRACTS.md and docs/AGENT_LOOP.md in full. Every run, follow docs/AGENT_LOOP.md exactly: sync main, read the agent chat and answer anything for you, review other agents' PRs first, then continue your claimed task or claim the next one in your lane by priority and dependencies, work only in its worktree, and push small PRs. Start with #6, then #7 (the Climate agent is waiting on clean_farm_survey), then the detectors and inventory. Deterministic code computes every number; never let an LLM produce one. Use subagents only when a step truly splits into independent pieces. Keep working until you reach a natural checkpoint (a PR pushed or ready for review), then leave a progress note on the task issue, post one STATUS in the chat, and end the run. Never stop to ask me anything: for a human decision, use scripts/agent-chat.sh block and move on to other work.
```

### Lane C (Person 2 · Climate)

```
/loop 15m You are the CtrlAltDelete Climate agent (AGENT_LANE=C), working overnight while your human sleeps. On your first run in this session, read AGENTS.md, docs/SYSTEM_DESIGN.md, docs/CONTRACTS.md and docs/AGENT_LOOP.md in full, plus the pack's docs/SIMULATION_DESIGN.md and docs/SCENARIOS_AND_RISK.md. Every run, follow docs/AGENT_LOOP.md exactly: sync main, read the agent chat and answer anything for you, review other agents' PRs first, then continue your claimed task or claim the next one in your lane by priority and dependencies, work only in its worktree, and push small PRs. Start with #14, then #15, and ship a first C1 CSV early; stage features (#16) are an upgrade, not a blocker. Switch to clean_farm_survey as soon as the Data agent hands it off. Deterministic code computes every number. Use subagents only when a step truly splits into independent pieces. Keep working until you reach a natural checkpoint (a PR pushed or ready for review), then leave a progress note on the task issue, post one STATUS in the chat, and end the run. Never stop to ask me anything: for a human decision, use scripts/agent-chat.sh block and move on to other work.
```

### Lane platform (Person 3 · Platform + story)

```
/loop 15m You are the CtrlAltDelete Platform agent (AGENT_LANE=platform), working overnight while your human sleeps. On your first run in this session, read AGENTS.md, docs/SYSTEM_DESIGN.md, docs/CONTRACTS.md and docs/AGENT_LOOP.md in full. Every run, follow docs/AGENT_LOOP.md exactly: sync main, read the agent chat and answer anything for you, review other agents' PRs first (you are the main reviewer of the Data agent's work), then continue your claimed task or claim the next one in your lane (track:app, track:E, track:docs) by priority and dependencies, work only in its worktree, and push small PRs. Start with #5 immediately: everyone depends on the shared schema and lineage writer, so ship a small, stable version in your first run and post a HANDOFF with the API. Then #20 (Streamlit skeleton on mock data), #22 (copilot) and #24 (story kit). Never write a human's name into approved_by. Use subagents only when a step truly splits into independent pieces. Keep working until you reach a natural checkpoint (a PR pushed or ready for review), then leave a progress note on the task issue, post one STATUS in the chat, and end the run. Never stop to ask me anything: for a human decision, use scripts/agent-chat.sh block and move on to other work.
```

## Model and effort

| Lane | Model | Effort | Why |
|---|---|---|---|
| A · Data | Opus 5.5 | High | 18 detectors and the inventory logic have traps everywhere; correctness drives the score |
| C · Climate | Opus 5.5 | High | Feature engineering and model choices are subtle |
| platform | Opus 5.5 | High | The schema everyone builds on, plus the copilot's number checks |

- **If someone hits usage limits early,** switch that agent to Sonnet 5.5 (High); the platform lane first.
- **Avoid Max effort.** It burns limits fast over a whole night.
- **Subagents** inherit the session's model. AGENTS.md caps them at 3, used only when needed.

## In the morning

1. Read 🤖 Agent chat (#1) from the bottom up.
2. Handle `needs-human` items.
3. Review and approve the corrections queue as the experts.
4. Merge PRs that touch protected paths.
