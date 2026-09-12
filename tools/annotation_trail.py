#!/usr/bin/env python3
"""Annotation -> revision audit trail for the IKT448 course script.

Sub-commands
  fetch   export annotations from the Hypothesis API (pseudonymised CSV + raw JSON)
  git     parse the repository history for Annotation/Type/Origin trailers
  join    match annotations to commits and write trail.csv + summary.md

Stdlib only. Run from the repository root.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import statistics
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("data")
API = "https://api.hypothes.is/api/search"
KIND_TAGS = {
    "question": "question",
    "correction": "correction",
    "practice example": "example",
    "example": "example",
}


# ---------------------------------------------------------------- helpers
def iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def pseudonym(user: str, salt: str) -> str:
    digest = hmac.new(salt.encode(), user.encode(), hashlib.sha256).hexdigest()
    return "S-" + digest[:6]


def chapter_of(uri: str) -> str:
    """'…/chapters/05-digital-security-act-and-nis2.html' -> 'ch05';
    '…/labs/exercise-03.html' -> 'lab03'."""
    m = re.search(r"/chapters/(\d{2})-", uri)
    if m:
        return f"ch{m.group(1)}"
    m = re.search(r"/labs/(?:exercise-)?(\d{2})", uri)
    if m:
        return f"lab{m.group(1)}"
    m = re.search(r"/appendix/([\w-]+)\.html", uri)
    if m:
        return f"app-{m.group(1)}"
    return "index" if uri.rstrip("/").endswith(("ikt448", "index.html")) else "other"


def site_url_from_remote() -> str:
    """github.com/<user>/<repo>(.git) -> https://<user>.github.io/<repo>/"""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                             text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        return ""
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    return f"https://{m.group(1)}.github.io/{m.group(2)}/" if m else ""


def quote_of(ann: dict) -> str:
    for target in ann.get("target", []):
        for sel in target.get("selector", []):
            if sel.get("type") == "TextQuoteSelector":
                return sel.get("exact", "")
    return ""


def kind_of(tags: list[str]) -> str:
    for t in tags:
        k = KIND_TAGS.get(t.strip().lower())
        if k:
            return k
    return "untagged"


# ---------------------------------------------------------------- fetch
def cmd_fetch(args: argparse.Namespace) -> None:
    token = os.environ.get("HYPOTHESIS_TOKEN")
    salt = os.environ.get("PSEUDO_SALT")
    if not salt:
        sys.exit("PSEUDO_SALT is not set – refuse to write un-salted pseudonyms.")
    if args.group and not token:
        sys.exit("HYPOTHESIS_TOKEN is required to read a private group.")

    DATA.mkdir(exist_ok=True)
    prefix = args.uri_prefix or site_url_from_remote()
    if not prefix:
        sys.exit("Cannot derive the site URL from the git remote – pass --uri-prefix.")
    params = {"limit": 200, "sort": "updated", "order": "asc",
              "wildcard_uri": prefix.rstrip("*") + "*"}
    if args.group:
        params["group"] = args.group

    rows: list[dict] = []
    search_after = None
    while True:
        q = dict(params)
        if search_after:
            q["search_after"] = search_after
        req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q))
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=60) as resp:
            page = json.load(resp)
        batch = page.get("rows", [])
        rows.extend(batch)
        if len(batch) < params["limit"]:
            break
        search_after = batch[-1]["updated"]

    (DATA / "annotations_raw.json").write_text(json.dumps(rows, indent=1))

    with (DATA / "annotations.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "created", "updated", "user", "chapter", "kind",
                    "is_reply", "parent", "tags", "quote", "text", "uri"])
        for a in rows:
            user = a.get("user", "")
            who = "instructor" if user == args.instructor else pseudonym(user, salt)
            refs = a.get("references") or []
            tags = a.get("tags") or []
            w.writerow([
                a["id"], a["created"], a["updated"], who,
                chapter_of(a.get("uri", "")), kind_of(tags),
                int(bool(refs)), refs[0] if refs else "",
                "|".join(tags), quote_of(a), a.get("text", ""), a.get("uri", ""),
            ])
    print(f"{len(rows)} annotations on {prefix} -> data/annotations.csv "
          "(raw JSON kept locally, gitignored)")


# ---------------------------------------------------------------- git
FMT = "%H%x1f%aI%x1f%s%x1f%(trailers:key=Annotation,valueonly,separator=;)" \
      "%x1f%(trailers:key=Type,valueonly)%x1f%(trailers:key=Origin,valueonly)%x1e"


def cmd_git(args: argparse.Namespace) -> None:
    DATA.mkdir(exist_ok=True)
    out = subprocess.run(["git", "log", f"--format={FMT}"], capture_output=True,
                         text=True, check=True).stdout
    with (DATA / "commits.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["hash", "date", "subject", "annotations", "type", "origin", "files"])
        n = 0
        for rec in out.split("\x1e"):
            rec = rec.strip("\n")
            if not rec:
                continue
            h, date, subj, anns, typ, origin = (rec.split("\x1f") + [""] * 6)[:6]
            ann_ids = [x.strip() for x in re.split(r"[;,\s]+", anns) if x.strip()]
            files = subprocess.run(["git", "show", "--format=", "--name-only", h],
                                   capture_output=True, text=True).stdout.split()
            w.writerow([h, date, subj, "|".join(ann_ids), typ.strip(), origin.strip(),
                        "|".join(files)])
            n += 1
    print(f"{n} commits -> data/commits.csv")


# ---------------------------------------------------------------- join
def cmd_join(args: argparse.Namespace) -> None:
    anns = list(csv.DictReader((DATA / "annotations.csv").open()))
    commits = list(csv.DictReader((DATA / "commits.csv").open()))

    by_ann: dict[str, list[dict]] = defaultdict(list)
    for c in commits:
        for aid in filter(None, c["annotations"].split("|")):
            by_ann[aid].append(c)

    trail = []
    for a in anns:
        hits = sorted(by_ann.get(a["id"], []), key=lambda c: c["date"])
        first = hits[0] if hits else None
        latency = ""
        if first:
            latency = round((iso(first["date"]) - iso(a["created"])).total_seconds() / 86400, 1)
        trail.append({
            **{k: a[k] for k in ("id", "created", "user", "chapter", "kind", "is_reply")},
            "revised": int(bool(first)),
            "commit": first["hash"][:10] if first else "",
            "commit_date": first["date"] if first else "",
            "type": first["type"] if first else "",
            "origin": first["origin"] if first else "",
            "latency_days": latency,
        })

    with (DATA / "trail.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(trail[0].keys()) if trail else ["id"])
        w.writeheader()
        w.writerows(trail)

    # ---- summary
    top = [t for t in trail if t["is_reply"] == "0"]      # top-level annotations only
    students = {t["user"] for t in top if t["user"] != "instructor"}
    revised = [t for t in top if t["revised"]]
    lat = [float(t["latency_days"]) for t in revised if t["latency_days"] != ""]

    def table(counter: Counter, head: str) -> str:
        lines = [f"| {head} | n |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in sorted(counter.items())]
        return "\n".join(lines)

    lines = [
        "# Annotation → revision summary",
        f"_generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC_", "",
        f"- annotations (top-level): **{len(top)}**, replies: {len(trail) - len(top)}",
        f"- annotating students (pseudonyms): **{len(students)}**",
        f"- annotations that led to a revision: **{len(revised)}** "
        f"({(100 * len(revised) / len(top)) if top else 0:.0f} %)",
        f"- median latency annotation→commit: "
        f"{statistics.median(lat):.1f} days" if lat else "- median latency: n/a", "",
        "## Per chapter", table(Counter(t["chapter"] for t in top), "chapter"), "",
        "## Per annotation kind (student tags)", table(Counter(t["kind"] for t in top), "kind"), "",
        "## Revisions per type", table(Counter(t["type"] or "?" for t in revised), "type"), "",
        "## Revisions per origin", table(Counter(t["origin"] or "?" for t in revised), "origin"), "",
        "## Annotations per student (distribution)",
        table(Counter(Counter(t["user"] for t in top if t["user"] != "instructor").values()),
              "annotations per student → students"),
    ]
    (DATA / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"{len(trail)} rows -> data/trail.csv; data/summary.md written")


# ---------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="export annotations from Hypothesis")
    f.add_argument("--group", help="Hypothesis group id (private course group)")
    f.add_argument("--uri-prefix", default="",
                   help="site URL; default derived from the git remote (<user>.github.io/<repo>/)")
    f.add_argument("--instructor", default="", help="your Hypothesis userid, e.g. acct:name@hypothes.is")
    sub.add_parser("git", help="parse commit trailers")
    sub.add_parser("join", help="join annotations and commits, write summary")
    args = p.parse_args()
    {"fetch": cmd_fetch, "git": cmd_git, "join": cmd_join}[args.cmd](args)


if __name__ == "__main__":
    main()
