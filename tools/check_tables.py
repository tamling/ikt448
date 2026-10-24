#!/usr/bin/env python3
"""Find pandoc simple/multiline tables whose cell text straddles a column boundary.

Pandoc cuts every row of a simple table at the column starts given by the
dashed line. If a cell's text runs past the start of the next column, the
word is split across two cells in the rendered page ("Di | sastrous").

Usage:  python3 tools/check_tables.py chapters appendix
Exit code 1 if anything is found.
"""
import pathlib
import re
import sys

DASH = re.compile(r"^\s*-{3,}(?:\s+-{3,})+\s*$")
found = 0
for root in sys.argv[1:] or ["chapters"]:
    for f in sorted(pathlib.Path(root).rglob("*.qmd")):
        if "_site" in f.parts:
            continue
        lines = f.read_text().split("\n")
        for i, line in enumerate(lines):
            if not DASH.match(line):
                continue
            starts = [m.start() for m in re.finditer(r"-+", line)][1:]
            block = []
            prev = lines[i - 1] if i else ""
            if prev.strip() and not set(prev.strip()) <= set("-") and not prev.lstrip().startswith((":::", "{#")):
                block.append(i - 1)
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].lstrip().startswith(":"):
                if not set(lines[j].strip()) <= set("-"):
                    block.append(j)
                j += 1
            for k in block:
                s = lines[k]
                for st in starts:
                    if st < len(s) and s[st - 1] != " " and s[st] != " ":
                        found += 1
                        print(f"{f}:{k + 1}: column at {st}: ...{s[max(0, st - 15):st]}|{s[st:st + 15]}...")
print(f"{found} split cell(s)" if found else "no split cells")
sys.exit(1 if found else 0)
