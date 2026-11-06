"""Plain-English progress report for the humans, posted to the pinned "📊 Progress reports" issue.

Run:  python3 scripts/progress_report.py           (post a report)
      python3 scripts/progress_report.py --print   (print only)

Reads only GitHub state (issues, PRs, agent chat) and files on origin/main, so any laptop can run it.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

EET = timezone(timedelta(hours=2))
FREEZE = datetime(2026, 11, 8, 6, 0, tzinfo=EET)
DEADLINE = datetime(2026, 11, 8, 10, 0, tzinfo=EET)
LANES = {"A · Data": {"track:A"}, "C · Climate": {"track:C"}, "Platform + story": {"track:app", "track:E", "track:docs"}}
CSVS = ["A1_issues_submission.csv", "A2_inventory_2025_submission.csv", "C1_yields_2027_2031_submission.csv",
        "C2_climate_yield_risk_submission.csv", "E_answers_submission.csv"]
REPORT_TITLE = "📊 Progress reports"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def gh_json(*args: str):
    return json.loads(gh(*args) or "null")


def report_issue() -> int:
    found = gh_json("issue", "list", "--state", "open", "--search", f"in:title {REPORT_TITLE}", "--json", "number,title")
    for i in found:
        if i["title"] == REPORT_TITLE:
            return i["number"]
    url = gh("issue", "create", "--title", REPORT_TITLE, "--body",
             "Automatic plain-English status for the humans: one comment every ~30 minutes. Newest at the bottom.").strip()
    n = int(url.rstrip("/").split("/")[-1])
    subprocess.run(["gh", "issue", "pin", str(n)], capture_output=True)
    return n


def last_report_time(n: int) -> datetime:
    comments = gh_json("api", f"repos/{{owner}}/{{repo}}/issues/{n}/comments?per_page=100", "--paginate")
    if not comments:
        return datetime.now(timezone.utc) - timedelta(minutes=30)
    return datetime.fromisoformat(comments[-1]["created_at"].replace("Z", "+00:00"))


def fmt_left(t: datetime) -> str:
    d = t - datetime.now(EET)
    if d.total_seconds() <= 0:
        return "passed"
    h, m = divmod(int(d.total_seconds() // 60), 60)
    return f"{h} h {m:02d} min"


def owner_of(issue_number: int) -> str:
    bodies = gh_json("api", f"repos/{{owner}}/{{repo}}/issues/{issue_number}/comments?per_page=100", "--paginate",
                     "--jq", '[.[].body | select(startswith("🔒 CLAIMED by [") or startswith("🔓 RELEASED"))]')
    owner = ""
    for b in bodies or []:
        if b.startswith("🔓"):
            owner = ""
        elif not owner:
            owner = b.split("[", 1)[1].split("]", 1)[0]
    return owner


def main() -> None:
    now = datetime.now(EET)
    issues = gh_json("issue", "list", "--label", "agent-task", "--state", "all", "--limit", "200",
                     "--json", "number,title,state,labels,closedAt")
    prs_open = gh_json("pr", "list", "--state", "open", "--limit", "50", "--json", "number,title,labels,reviewDecision")
    prs_merged = gh_json("pr", "list", "--state", "merged", "--limit", "50", "--json", "number,title,mergedAt")
    n = report_issue()
    since = last_report_time(n)
    gh("api", "repos/{owner}/{repo}/git/refs/heads/main")  # fail early if offline
    out_files = set(gh_json("api", "repos/{owner}/{repo}/contents/out", "--jq", "[.[].name]") or [])

    lines = [f"## {now:%a %H:%M} EET · freeze in {fmt_left(FREEZE)} · deadline in {fmt_left(DEADLINE)}", ""]
    total = len(issues)
    done = sum(i["state"] == "CLOSED" for i in issues)
    lines.append(f"**Overall: {done}/{total} tasks done ({done * 100 // max(total, 1)} %).**")
    csv_have = [c for c in CSVS if c in out_files]
    lines.append(f"**Submission CSVs on main: {len(csv_have)}/5**: " +
                 ", ".join(("✅ " if c in out_files else "⬜ ") + c.split("_")[0] for c in CSVS))
    cp1 = any(i["number"] == 5 and i["state"] == "CLOSED" for i in issues)
    checkpoint = "4 · frozen" if now >= FREEZE else "2 · first end-to-end (all CSVs)" if len(csv_have) == 5 else \
        "1 · shared schema done, building toward all CSVs" if cp1 else "0 · setting up"
    lines += [f"**Checkpoint reached: {checkpoint}**", "", "### By lane", "",
              "| Lane | Done | In progress | To do | Needs a human |", "|---|---|---|---|---|"]
    for lane, labels in LANES.items():
        mine = [i for i in issues if labels & {l["name"] for l in i["labels"]}]
        prog = [i for i in mine if i["state"] == "OPEN" and any(l["name"] == "status:claimed" for l in i["labels"])]
        human = [i for i in mine if i["state"] == "OPEN" and any(l["name"] == "needs-human" for l in i["labels"])]
        todo = [i for i in mine if i["state"] == "OPEN" and i not in prog]
        prog_txt = "; ".join(f"#{i['number']} {re.sub(r'^\[P\d\] ', '', i['title'])[:45]} ({owner_of(i['number']) or '?'})" for i in prog) or "—"
        lines.append(f"| {lane} | {sum(i['state'] == 'CLOSED' for i in mine)}/{len(mine)} | {prog_txt} | {len(todo)} | "
                     f"{', '.join('#' + str(i['number']) for i in human) or '—'} |")

    merged = [p for p in prs_merged if datetime.fromisoformat(p["mergedAt"].replace("Z", "+00:00")) > since]
    lines += ["", f"### Landed since last report ({len(merged)})"]
    lines += [f"- #{p['number']} {p['title']}" for p in merged] or ["- nothing merged"]
    lines += ["", f"### Waiting for review ({len(prs_open)})"]
    lines += [f"- #{p['number']} {p['title']}" + (" · **needs a human**" if any(l["name"] == "needs-human" for l in p["labels"])
                                                  or "human" in p["title"].lower() else "") for p in prs_open] or ["- none"]

    chat = gh_json("issue", "list", "--label", "agent-chat", "--state", "open", "--json", "number")
    if chat:
        msgs = gh_json("api", f"repos/{{owner}}/{{repo}}/issues/{chat[0]['number']}/comments?per_page=100", "--paginate",
                       "--jq", "[.[] | .body]")
        latest: dict[str, str] = {}
        for b in msgs or []:
            m = re.match(r"\*\*\[([a-z0-9-]+)\]\*\* (.*)", b.replace("\n", " "))
            if m and m.group(2).startswith(("STATUS", "DONE", "BLOCKED", "IDLE")):
                latest[m.group(1)] = m.group(2)
        lines += ["", "### What each agent said last"]
        lines += [f"- **{a}**: {t[:280]}" for a, t in latest.items()] or ["- no status yet"]

    try:
        sb = gh("api", "repos/{owner}/{repo}/contents/docs/SCOREBOARD.md", "-H", "Accept: application/vnd.github.raw")
        table = sb.split("## Current status", 1)[1].split("## ", 1)[0].strip()
        lines += ["", "### Scoreboard (docs/SCOREBOARD.md)", "", table]
    except subprocess.CalledProcessError:
        pass

    body = "\n".join(lines)
    if "--print" in sys.argv:
        print(body)
    else:
        gh("issue", "comment", str(n), "--body", body)
        print(f"posted report to #{n}")


if __name__ == "__main__":
    main()
