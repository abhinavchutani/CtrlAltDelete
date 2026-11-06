#!/usr/bin/env bash
# agent-chat.sh: GitHub-based coordination for the team's AI agents.
# Chat = the open issue labelled `agent-chat`. Tasks = issues labelled `agent-task`.
# Requires: git, gh (authenticated). Works with macOS bash 3.2.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "run this inside the repo" >&2; exit 1; }
MAIN_ROOT="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)"   # main checkout, also from a worktree
cd "$ROOT"

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

env_value() {  # env_value KEY → value from env or .env (worktree first, then main checkout)
  local key="$1" val="${!1:-}" f
  if [ -z "$val" ]; then
    for f in "$ROOT/.env" "$MAIN_ROOT/.env"; do
      if [ -f "$f" ]; then
        val="$(grep -E "^${key}=" "$f" | tail -1 | cut -d= -f2- | tr -d "\"' ")"
        [ -n "$val" ] && break
      fi
    done
  fi
  printf '%s' "$val"
}

load_name() {
  AGENT_NAME="$(env_value AGENT_NAME)"
  if ! printf '%s' "$AGENT_NAME" | grep -Eq '^[a-z0-9][a-z0-9-]{1,30}$'; then
    echo "AGENT_NAME missing or invalid. Set it in .env (lowercase letters, digits, dashes)." >&2
    exit 1
  fi
}

chat_issue() {
  local n
  n="$(gh issue list --label agent-chat --state open --limit 1 --json number --jq '.[0].number // empty')"
  [ -n "$n" ] || { echo "no open issue labelled agent-chat" >&2; exit 1; }
  printf '%s' "$n"
}

is_task() {
  local labels
  labels="$(gh issue view "$1" --json labels,state --jq '"\(.state) " + ([.labels[].name] | join(","))')"
  case "$labels" in
    OPEN*agent-task*) return 0 ;;
    *) echo "#$1 is not an open agent-task issue" >&2; exit 2 ;;
  esac
}

current_owner() {  # current_owner ISSUE → the agent holding it, or empty
  local n="$1" owner="" line name
  while IFS= read -r line; do
    case "$line" in
      "🔓 RELEASED"*) owner="" ;;
      "🔒 CLAIMED by ["*)
        if [ -z "$owner" ]; then
          name="${line#"🔒 CLAIMED by ["}"
          owner="${name%%]*}"
        fi ;;
    esac
  done < <(gh api "repos/{owner}/{repo}/issues/$n/comments?per_page=100" --paginate \
            --jq '.[].body | select(startswith("🔒 CLAIMED by [") or startswith("🔓 RELEASED")) | gsub("\n"; " ")')
  printf '%s' "$owner"
}

my_tasks() {
  local n
  for n in $(gh issue list --label agent-task --label status:claimed --state open --limit 100 --json number --jq '.[].number'); do
    [ "$(current_owner "$n")" = "$AGENT_NAME" ] && echo "$n"
  done
  return 0
}

cmd_whoami() {
  load_name
  echo "agent:   $AGENT_NAME"
  echo "lane:    $(env_value AGENT_LANE)"
  echo "github:  $(gh api user --jq .login)"
  echo "repo:    $(gh repo view --json nameWithOwner --jq .nameWithOwner)"
  echo "chat:    #$(chat_issue)"
}

cmd_read() {
  local n="${1:-20}" chat
  chat="$(chat_issue)"
  gh api "repos/{owner}/{repo}/issues/$chat/comments?per_page=100" --paginate \
    --jq '.[] | "\(.created_at | sub("T"; " ") | sub("Z"; ""))  \(.body | gsub("\r"; "") | gsub("\n"; "  ⏎ "))"' \
    | tail -n "$n"
}

cmd_say() {
  load_name
  local msg="${*:-}" chat
  [ -n "$msg" ] || { echo 'usage: say "STATUS: …"' >&2; exit 1; }
  chat="$(chat_issue)"
  gh issue comment "$chat" --body "**[$AGENT_NAME]** $msg" >/dev/null
  echo "posted to #$chat"
}

cmd_tasks() {
  gh issue list --label agent-task --state open --limit 100 --json number,title,labels \
    --jq 'sort_by(.number) | .[] | "#\(.number)\t[\([.labels[].name | select(startswith("status:") or startswith("track:") or . == "needs-human")] | join(" "))]\t\(.title)"'
}

cmd_mine() {
  load_name
  local n
  for n in $(my_tasks); do
    gh issue view "$n" --json number,title --jq '"#\(.number)\t\(.title)"'
  done
}

cmd_owner() {
  local n="${1:?usage: owner ISSUE}" o
  o="$(current_owner "$n")"
  echo "${o:-nobody}"
}

cmd_claim() {
  load_name
  local n="${1:?usage: claim ISSUE}" owner held
  is_task "$n"
  owner="$(current_owner "$n")"
  if [ "$owner" = "$AGENT_NAME" ]; then echo "you already hold #$n"; return 0; fi
  if [ -n "$owner" ]; then echo "#$n is claimed by $owner" >&2; exit 2; fi
  held="$(my_tasks | head -1)"
  if [ -n "$held" ]; then echo "you already hold #$held. Release it first (one task at a time)." >&2; exit 2; fi
  gh issue comment "$n" --body "🔒 CLAIMED by [$AGENT_NAME] at $(now)" >/dev/null
  sleep 3
  owner="$(current_owner "$n")"
  if [ "$owner" != "$AGENT_NAME" ]; then
    gh issue comment "$n" --body "↩️ [$AGENT_NAME] yields #$n to [$owner], who claimed it first" >/dev/null
    echo "lost the race: #$n belongs to $owner" >&2
    exit 2
  fi
  gh issue edit "$n" --add-label status:claimed >/dev/null
  gh issue edit "$n" --remove-label status:todo >/dev/null 2>&1 || true
  echo "claimed #$n"
}

cmd_release() {
  load_name
  local n="${1:?usage: release ISSUE [note]}" note="${2:-}" owner
  owner="$(current_owner "$n")"
  [ "$owner" = "$AGENT_NAME" ] || { echo "#$n is held by ${owner:-nobody}, not you" >&2; exit 2; }
  gh issue comment "$n" --body "🔓 RELEASED by [$AGENT_NAME] at $(now)${note:+: $note}" >/dev/null
  gh issue edit "$n" --remove-label status:claimed >/dev/null 2>&1 || true
  gh issue edit "$n" --add-label status:todo >/dev/null
  echo "released #$n"
}

cmd_takeover() {
  load_name
  local n="${1:?usage: takeover ISSUE \"reason\"}" why="${2:?give a reason (stale claim, owner asked, …)}" owner
  owner="$(current_owner "$n")"
  [ -n "$owner" ] && [ "$owner" != "$AGENT_NAME" ] || { echo "nothing to take over (owner: ${owner:-nobody})" >&2; exit 2; }
  gh issue comment "$n" --body "🔓 RELEASED by [$AGENT_NAME] (takeover from [$owner]) at $(now): $why" >/dev/null
  cmd_say "HANDOFF: taking over #$n from @agent:$owner. $why"
  cmd_claim "$n"
}

cmd_start() {  # start ISSUE SLUG → worktree on agent/<name>/<issue>-<slug>, prints its path
  load_name
  local n="${1:?usage: start ISSUE slug}" slug="${2:?usage: start ISSUE slug}" owner dir br p
  printf '%s' "$slug" | grep -Eq '^[a-z0-9][a-z0-9-]{0,40}$' || { echo "slug: lowercase letters, digits, dashes" >&2; exit 1; }
  owner="$(current_owner "$n")"
  [ "$owner" = "$AGENT_NAME" ] || { echo "claim #$n first (owner: ${owner:-nobody})" >&2; exit 2; }
  dir="$MAIN_ROOT/.worktrees/$n"
  br="agent/$AGENT_NAME/$n-$slug"
  git -C "$MAIN_ROOT" fetch -q origin
  if [ ! -d "$dir" ]; then
    if git -C "$MAIN_ROOT" show-ref --verify --quiet "refs/heads/$br"; then
      git -C "$MAIN_ROOT" worktree add -q "$dir" "$br"
    elif git -C "$MAIN_ROOT" show-ref --verify --quiet "refs/remotes/origin/$br"; then
      git -C "$MAIN_ROOT" worktree add -q --track -b "$br" "$dir" "origin/$br"
    else
      git -C "$MAIN_ROOT" worktree add -q -b "$br" "$dir" origin/main
    fi
  fi
  # Share local-only, gitignored files with the worktree
  [ -e "$dir/.env" ] || [ ! -f "$MAIN_ROOT/.env" ] || ln -s "$MAIN_ROOT/.env" "$dir/.env"
  [ -e "$dir/.venv" ] || [ ! -d "$MAIN_ROOT/.venv" ] || ln -s "$MAIN_ROOT/.venv" "$dir/.venv"
  mkdir -p "$dir/data"
  for p in "$MAIN_ROOT"/data/*/; do
    [ -d "$p" ] || continue
    p="${p%/}"
    [ -e "$dir/data/$(basename "$p")" ] || ln -s "$p" "$dir/data/$(basename "$p")"
  done
  echo "$dir"
}

cmd_reviews() {
  load_name
  gh pr list --state open --label status:in-review --limit 50 \
    --json number,title,headRefName,reviewDecision \
    --jq '.[] | "#\(.number)\t\(.reviewDecision // "NO_REVIEW")\t\(.headRefName)\t\(.title)"' \
    | grep -v "agent/$AGENT_NAME/" || true
}

cmd_block() {
  load_name
  local n="${1:?usage: block ISSUE \"question\"}"
  shift
  local why="${*:?say what the human needs to decide}"
  gh issue edit "$n" --add-label needs-human >/dev/null
  gh issue comment "$n" --body "🙋 [$AGENT_NAME] needs a human: $why" >/dev/null
  cmd_say "BLOCKED: #$n needs a human: $why"
}

cmd_new_task() {
  load_name
  local title="${1:?usage: new-task \"title\" \"body\" [A|C|E|app|docs]}" body="${2:-}" track="${3:-}"
  local args=(--title "$title" --body "${body}

_Created by [$AGENT_NAME]_" --label agent-task --label status:todo)
  [ -n "$track" ] && args+=(--label "track:$track")
  gh issue create "${args[@]}"
}

usage() {
  cat <<'EOF'
agent-chat.sh: coordinate AI agents through GitHub (see AGENTS.md)

  whoami                      show agent name, lane, GitHub user, chat issue
  read [N]                    last N chat messages (default 20)
  say "TYPE: message"         post to the chat (TYPE = STATUS|CLAIM|HANDOFF|QUESTION|REVIEW|BLOCKED|IDLE)
  tasks                       open agent-task issues with status/track labels
  mine                        tasks you currently hold
  owner ISSUE                 who holds a task
  claim ISSUE                 claim a task (one at a time; first claim wins)
  release ISSUE [note]        give a task back
  takeover ISSUE "reason"     take over a stale task (see AGENTS.md §4)
  start ISSUE slug            worktree .worktrees/ISSUE on agent/<name>/ISSUE-slug (links .env, .venv, data)
  reviews                     PRs waiting for review that you did not write
  block ISSUE "question"      label needs-human, explain, and announce in chat
  new-task "title" "body" [A|C|E|app|docs]   create a task issue
EOF
}

cmd="${1:-help}"
shift || true
case "$cmd" in
  whoami)   cmd_whoami ;;
  read)     cmd_read "$@" ;;
  say)      cmd_say "$@" ;;
  tasks)    cmd_tasks ;;
  mine)     cmd_mine ;;
  owner)    cmd_owner "$@" ;;
  claim)    cmd_claim "$@" ;;
  release)  cmd_release "$@" ;;
  takeover) cmd_takeover "$@" ;;
  start)    cmd_start "$@" ;;
  reviews)  cmd_reviews ;;
  block)    cmd_block "$@" ;;
  new-task) cmd_new_task "$@" ;;
  help|-h|--help) usage ;;
  *) echo "unknown command: $cmd" >&2; usage; exit 1 ;;
esac
