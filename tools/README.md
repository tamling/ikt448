# Annotation → revision audit trail (IKT448 · GRC1100 · SKY2100 · TK1104)

> **IKT448 course group:** `XjreopNx`
> ([IKT 448 2026](https://hypothes.is/groups/XjreopNx/ikt-448-2026)) —
> export with `python3 tools/annotation_trail.py fetch --group XjreopNx`.

Two small pieces: a commit template that records which Hypothesis
annotation caused a change, and a script that exports the annotations,
parses the git history, joins the two and writes a summary.

## One-time setup (per repo, after the `tools:` commit is in)

```bash
git config commit.template tools/commit-template.txt
```

`data/annotations_raw.json` is already in `.gitignore` — it contains real
usernames and must never be committed.

Environment variables (put them in `~/.bashrc` or a `.env` you don't commit):

```bash
export HYPOTHESIS_TOKEN="…"        # hypothes.is → Settings → Developer → API token
export PSEUDO_SALT="long-random-string"   # keep constant for the whole study
```

## Daily use

Every change that goes back to a student annotation gets its own commit
(one annotation → one commit, or one commit for several annotations that
raise the *same* issue). `git commit` opens the template; uncomment and
fill the three trailer lines. Changes with no annotation behind them
(your own edits) need no trailers.

## Export, coding and analysis

```bash
python3 tools/annotation_trail.py fetch --group <GROUP_ID> [--uri-prefix https://<site>/]
python3 tools/annotation_trail.py git
python3 tools/annotation_trail.py sheet --coder A      # data/coding_A.xlsx with dropdowns
python3 tools/annotation_trail.py sheet --coder B      # same for the second coder
#   ... code in Excel/LibreOffice, save in place ...
python3 tools/annotation_trail.py kappa data/coding_A.xlsx data/coding_B.xlsx
python3 tools/annotation_trail.py join --coding data/coding_A.xlsx
```

Group ids: IKT448 `XjreopNx`, GRC1100 `A6mEpoeV`, SKY2100 `4Ndo1RnJ`. Run `fetch` once
without `--group` now and then to catch annotations students posted to
"Public" by mistake.

The site URL is derived from the git remote (`tamling.github.io/<repo>/`); override with `--uri-prefix` if needed. `--group` is the Hypothesis group id (from the group URL
`hypothes.is/groups/<id>/…`). Without `--group` the script pulls public
annotations on the site, which is what you have until a course group is
configured — configure one; public annotations are visible to anyone
and complicate the Sikt notification.

Add `--instructor acct:yourname@hypothes.is` so your own annotations
are labelled `instructor` instead of getting a student pseudonym.

Outputs in `data/`:

| file | content |
|---|---|
| `annotations_raw.json` | untouched API export (gitignored) |
| `annotations.csv` | one row per annotation, pseudonymised |
| `commits.csv` | one row per commit with trailers |
| `coding_<coder>.xlsx` | coding sheet: id, chapter, student tag, quote, text + dropdown columns `kind_coded`, `subtype`, `topic`, `valid`, `note` |
| `trail.csv` | one row per annotation: coded columns, revised? which commit, type, origin, latency (days) |
| `summary.md` | counts per chapter, per annotation kind, revision rate, latency, origin split |

Run `fetch` again any time; it overwrites the exports. Re-run `join`
after new commits.

## Annotation kinds

Coding happens in `coding_<coder>.xlsx`, never in the CSV exports (they are overwritten by `fetch`). The codebook is on the second sheet of the workbook.

`annotations.csv` has a `chapter` column (`chNN`; SKY2100 labs `labNN`) and a `kind` column derived from Hypothesis tags,
matching the categories students are told to use in the script's
"How to annotate" appendix: `question`, `correction`, `example`. Anything
else is `untagged` and needs manual coding — do that in a copy of the
CSV, not in the export.
