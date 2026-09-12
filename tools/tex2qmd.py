#!/usr/bin/env python3
"""Convert legacy/IKT448_Script.tex into the Quarto book sources.

The LaTeX script is generated from the session decks (tools/build_script.py
in the deck repository) and is therefore very regular; this converter relies
on that regularity. It writes

  chapters/NN-slug.qmd      one chapter per session (wording unchanged)
  answers/NN-slug.qmd       the \\answer{} texts, moved out of the chapters
  _tikz/fig-NN-k.tikz       every tikzpicture, built to SVG by _tikz/build.sh
  index.qmd, how-to-use.qmd the front matter
  appendix/reading-list.qmd every chapter's Sources, by first appearance

and prints the chapter list for _quarto.yml. Run from the repository root:

  python3 tools/tex2qmd.py            # convert
  python3 tools/tex2qmd.py --list     # list figures/tables with their captions

Captions for figures and tables are kept in tools/captions.json (keyed by
the figure/table id); an entry that is missing falls back to the heading
of the subsection the figure or table sits in.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "legacy" / "IKT448_Script.tex"
CAPTIONS = ROOT / "tools" / "captions.json"

SLUGS = {
    1: "introduction",
    2: "approaches-to-research",
    3: "purpose-and-products",
    4: "research-questions",
    5: "reviewing-the-literature",
    6: "strategies-survey-design-experiment",
    7: "strategies-case-action-ethnography",
    8: "quantitative-data",
    9: "qualitative-data",
    10: "ethics",
    11: "producing-the-essay",
    12: "summing-up",
}

MATH = {
    r"$\rightarrow$": "→",
    r"$\leftarrow$": "←",
    r"$\leftrightarrow$": "↔",
    r"$\cdot$": "·",
    r"$\times$": "×",
    r"$\sim$": "~",
    r"$\neq$": "≠",
    r"$\approx$": "≈",
    r"$\bullet$": "•",
    r"$\blacktriangleright$": "▶",
    r"$+$": "+",
    r"$=$": "=",
    r"$<$": "<",
    r"$R^2$": "R²",
    r"$f^2$": "f²",
    r"$Q^2$": "Q²",
    r"$\alpha$": "α",
    r"$\Omega$": "Ω",
    r"$\Lambda$": "Λ",
    r"$p$": r"\emph{p}",
    r"$p = 0.03$": r"\emph{p} = 0.03",
}


# ---------------------------------------------------------------- helpers
def pandoc(tex: str) -> str:
    out = subprocess.run(
        ["pandoc", "-f", "latex", "-t", "markdown-raw_attribute", "--wrap=none", "--top-level-division=chapter"],
        input=tex, capture_output=True, text=True, check=True,
    ).stdout
    return out.strip("\n")


def slugify(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)          # drop commands
    s = re.sub(r"[{}$]", "", s)
    s = s.replace("---", " ").replace("--", " ").replace("&", " and ")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s


def balanced(text: str, start: int) -> int:
    """Index just past the brace group that opens at text[start] == '{'."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced braces")


def replace_cmd(text: str, cmd: str, fn, nargs: int = 1) -> str:
    """Replace every \\cmd{a}{b}... (nargs brace groups) by fn(args)."""
    pat = re.compile(r"\\" + cmd + r"(?![a-zA-Z])\s*")
    out, pos = [], 0
    while True:
        m = pat.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        i = m.end()
        args = []
        for _ in range(nargs):
            if i >= len(text) or text[i] != "{":
                break
            j = balanced(text, i)
            args.append(text[i + 1:j - 1])
            i = j
        out.append(fn(args) if len(args) == nargs else m.group(0))
        pos = i
    return "".join(out)


def replace_group(text: str, opener: str, fn) -> str:
    """Replace {<opener> ...} groups (e.g. {\\color{uiared}\\bfseries X})."""
    pat = re.compile(r"\{" + opener)
    out, pos = [], 0
    while True:
        m = pat.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        j = balanced(text, m.start())
        inner = text[m.end():j - 1]
        out.append(text[pos:m.start()])
        out.append(fn(inner))
        pos = j
    return "".join(out)


def heading_before(text: str, pos: int) -> str:
    best = None
    for m in re.finditer(r"\\(?:sub)?section\*?\{([^}]*)\}", text[:pos]):
        best = m.group(1)
    return best or ""


# ------------------------------------------------------------ preprocess
class Chapter:
    def __init__(self, no: int, title: str, part: str, tex: str):
        self.no, self.title, self.part, self.tex = no, title, part, tex
        self.slug = SLUGS[no]
        self.figs: list[tuple[str, str, str]] = []    # (id, tikz, default caption)
        self.tbls: list[tuple[str, str]] = []         # (id, default caption)
        self.answers: dict[str, list[tuple[str, str]]] = {}   # section -> [(question tex, answer tex)]
        self.sources: list[str] = []
        self.tail: dict[str, str] = {}                # unnumbered trailing sections

    @property
    def nn(self) -> str:
        return f"{self.no:02d}"


def fix_colspecs(tex: str) -> str:
    """L{w} (raggedright column type of the script) -> p{w}, which pandoc knows."""
    out, pos = [], 0
    pat = re.compile(r"\\begin\{tabular\}")
    while True:
        m = pat.search(tex, pos)
        if not m:
            out.append(tex[pos:])
            break
        j = balanced(tex, m.end())
        out.append(tex[pos:m.end()])
        out.append(tex[m.end():j].replace("L{", "p{"))
        pos = j
    return "".join(out)


def strip_layout(tex: str) -> str:
    tex = re.sub(r"\\begin\{center\}", "", tex)
    tex = re.sub(r"\\end\{center\}", "", tex)
    tex = re.sub(r"\\begin\{columns\}(\[[^\]]*\])?", "", tex)
    tex = re.sub(r"\\end\{columns\}", "", tex)
    tex = re.sub(r"\\begin\{column\}\{[^}]*\}", "", tex)
    tex = re.sub(r"\\end\{column\}", "", tex)
    tex = re.sub(r"\\column\{[^}]*\}", "", tex)
    tex = re.sub(r"\\begin\{minipage\}(\[[^\]]*\])?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\end\{minipage\}", "", tex)
    tex = re.sub(r"\\resizebox\{[^}]*\}\{!\}\{%?", "", tex)
    tex = re.sub(r"\\renewcommand\{\\arraystretch\}\{[^}]*\}", "", tex)
    tex = re.sub(r"\\setlength\{\\itemsep\}\{[^}]*\}", "", tex)
    tex = re.sub(r"\\vspace\*?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\(centering|raggedright|small|footnotesize|scriptsize|normalsize|medskip|smallskip|noindent|hfill|par|quad)(?![a-zA-Z])", "", tex)
    tex = re.sub(r"\\label\{ch:\d+\}\n?", "", tex)
    tex = replace_cmd(tex, "onionloc", lambda a: "", nargs=7)
    return tex


def convert_inline_styles(tex: str) -> str:
    tex = replace_group(tex, r"\\color\{uiared\}\\bfseries\s*", lambda s: r"\textbf{" + s.strip() + "}")
    tex = replace_group(tex, r"\\color\{(?:uiagrey|kgrey)\}\s*(?:\\(?:small|scriptsize|footnotesize)\s*)?", lambda s: r"\textit{" + s.strip() + "}")
    tex = replace_cmd(tex, "src", lambda a: r"\textit{" + a[0].strip() + "}")
    tex = replace_cmd(tex, "textcolor", lambda a: a[1], nargs=2)
    for k, v in MATH.items():
        tex = tex.replace(k, v)
    tex = re.sub(r"\$\\geq\s*([0-9.]+)\$", r"≥ \1", tex)
    tex = re.sub(r"\$<\s*([0-9.]+)\$", r"<\1", tex)
    return tex


def extract_answers(ch: Chapter, section: str, body: str) -> str:
    """Pull \\answer{} out of an enumerate; remember (question, answer) pairs."""
    items = re.split(r"\\item\s+", body)
    pairs = []
    kept = []
    for it in items[1:]:
        m = re.search(r"\\answer\s*\{", it)
        if m:
            j = balanced(it, m.end() - 1)
            q, a = it[:m.start()], it[m.end():j - 1]
            rest = it[j:]
        else:
            q, a, rest = it, "", ""
        q = re.sub(r"\s+", " ", q).strip()
        a = re.sub(r"\s+", " ", a).strip()
        pairs.append((q, a))
        kept.append(q + rest)
    ch.answers[section] = pairs
    return pairs


def question_title(q: str, n: int, section: str) -> str:
    m = re.match(r"\\textbf\{([^}]*)\}", q)
    if m:
        t = m.group(1)
    else:
        m = re.search(r"\\textbf\{([^}]*)\}", q)
        t = m.group(1) if m else f"Reading question {n}"
        t = t[:1].upper() + t[1:]
    t = t.strip().rstrip(":—-– ").strip()
    return t


def preprocess(ch: Chapter) -> str:
    tex = ch.tex
    # --- session head
    tex = replace_cmd(
        tex, "sessionhead",
        lambda a: "\\begin{sessionhead}\n\\textbf{Session %s} $\\cdot$ %s\n\\end{sessionhead}\n" % (a[0], a[1]),
        nargs=2)
    # --- split off the unnumbered end sections
    parts = re.split(r"\n\\section\*\{([^}]*)\}\n", tex)
    main = parts[0]
    for name, body in zip(parts[1::2], parts[2::2]):
        ch.tail[name] = body
    # --- figures
    def fig(m):
        k = len(ch.figs) + 1
        fid = f"fig-{ch.nn}-{k}"
        ch.figs.append((fid, m.group(2), heading_before(main, m.start())))
        tail = "" if m.group(1) else (m.group(3) or "")   # keep a brace that is not the resizebox's
        return "\\begin{figure}\\centering\\includegraphics{figures/%s.svg}\\caption{FIGCAP:%s}\\label{%s}\\end{figure}\n%s" % (fid, fid, fid, tail)
    main = re.sub(r"(\\resizebox\{[^}]*\}\{!\}\{%?\s*)?(\\begin\{tikzpicture\}.*?\\end\{tikzpicture\})(\})?", fig, main, flags=re.S)
    # --- tables
    def tbl(m):
        k = len(ch.tbls) + 1
        tid = f"tbl-{ch.nn}-{k}"
        ch.tbls.append((tid, heading_before(main, m.start())))
        return "\\begin{tblwrap}\n%s\n\nTBLCAP:%s\n\\end{tblwrap}\n" % (m.group(0), tid)
    main = fix_colspecs(main)
    main = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", tbl, main, flags=re.S)
    # --- blocks: title as a \paragraph so pandoc keeps inline markup
    main = re.sub(r"\\begin\{(block|alertblock)\}\{", lambda m: "\\begin{%s}\\paragraph{" % m.group(1), main)
    main = strip_layout(main)
    main = convert_inline_styles(main)
    return main


# ------------------------------------------------------------ postprocess
def add_heading_ids(md: str, nn: str) -> str:
    out = []
    for line in md.split("\n"):
        m = re.match(r"^(##) (.+?)(\s*\{\.unnumbered\})?$", line)
        if m:
            title = m.group(2)
            unnum = " .unnumbered" if m.group(3) else ""
            line = f"## {title} {{#sec-{nn}-{slugify(title)}{unnum}}}"
        out.append(line)
    return "\n".join(out)


def postprocess(md: str, ch: Chapter, captions: dict) -> str:
    md = add_heading_ids(md, ch.nn)
    # block divs -> callouts, first heading in the div is the title
    def blk(m):
        cls = {"block": "callout-note", "alertblock": "callout-important"}[m.group(1)]
        return "::: {.%s}\n## %s\n" % (cls, m.group(2).strip())
    md = re.sub(r"^::: (block|alertblock)\n#{4,5} (.+)\n", blk, md, flags=re.M)
    md = re.sub(r"^::: sessionhead\n", '::: {.callout-note appearance="simple" icon="false"}\n', md, flags=re.M)
    # table wrappers
    md = re.sub(r"^::: tblwrap\n(.*?)\n\nTBLCAP:(tbl-[\d-]+)\n:::",
                lambda m: "::: {#%s}\n%s\n\n%s\n:::" % (m.group(2), m.group(1), captions.get(m.group(2), default_caption(ch, m.group(2)))),
                md, flags=re.M | re.S)
    md = re.sub(r"FIGCAP:(fig-[\d-]+)", lambda m: captions.get(m.group(1), default_caption(ch, m.group(1))), md)
    # pandoc writes a chapter heading as "# Title"
    md = re.sub(r"^# (.+)$", lambda m: f"# {m.group(1)} {{#sec-{ch.nn}-{ch.slug}}}", md, count=1, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md


def default_caption(ch: Chapter, key: str) -> str:
    for fid, _, h in ch.figs:
        if fid == key:
            return pandoc_inline(h)
    for tid, h in ch.tbls:
        if tid == key:
            return pandoc_inline(h)
    return key


def pandoc_inline(tex: str) -> str:
    return pandoc(tex).replace("\n", " ") if tex else ""


def render_questions(ch: Chapter, section: str, captions: dict) -> tuple[str, str]:
    """Return (chapter markdown, answer-key markdown) for a question section."""
    pairs = ch.answers[section]
    used = set()
    chap, key = [], []
    heading = f"## {section} {{#sec-{ch.nn}-{slugify(section)} .unnumbered}}"
    chap.append(heading + "\n")
    key.append(f"## {section}\n")
    for n, (q, a) in enumerate(pairs, 1):
        title = question_title(q, n, section)
        eid = f"exr-{ch.nn}-{slugify(title)}"
        if eid in used:
            eid += f"-{n}"
        used.add(eid)
        qmd = pandoc(convert_inline_styles(strip_layout(q)))
        chap.append(f"::: {{#{eid}}}\n## {pandoc_inline(title)}\n\n{qmd}\n:::\n")
        amd = pandoc(convert_inline_styles(strip_layout(a))) if a else "*(no sketch answer in the source)*"
        key.append(f"{n}. **{pandoc_inline(title)}** (@{eid}) — {amd}\n")
    return "\n".join(chap), "\n".join(key)


def render_tail(ch: Chapter, captions: dict) -> tuple[str, str]:
    """The unnumbered end sections, in source order; answers go to the key."""
    chap, key = [], []
    for name, body in ch.tail.items():
        if name in ("Questions from the reading", "Questions for discussion"):
            extract_answers(ch, name, body)
            c, k = render_questions(ch, name, captions)
            chap.append(c)
            key.append(k)
            inter = ROOT / "chapters" / f"_{ch.nn}-interactive.qmd"
            if name == "Questions for discussion" and inter.exists():
                chap.append(f"## Interactive exercises {{#sec-{ch.nn}-interactive-exercises .unnumbered}}\n\n"
                            "Sort, order and pick: every exercise below is answerable from this chapter and checks itself.\n\n"
                            f"{{{{< include _{ch.nn}-interactive.qmd >}}}}\n")
            continue
        if name == "Sources":
            ch.sources = [re.sub(r"\s+", " ", s).strip() for s in re.split(r"\\item\s+", body)[1:]]
            ch.sources = [re.sub(r"\\end\{itemize\}.*$", "", s, flags=re.S).strip() for s in ch.sources]
        b = body
        if name == "Terms from this session":
            tid = f"tbl-{ch.nn}-terms"
            b = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}",
                       lambda m: "\\begin{tblwrap}\n%s\n\nTBLCAP:%s\n\\end{tblwrap}\n" % (m.group(0), tid), b, flags=re.S)
            ch.tbls.append((tid, f"Terms from Session {ch.no}"))
        md = pandoc(convert_inline_styles(strip_layout(b)))
        md = re.sub(r"^::: tblwrap\n(.*?)\n\nTBLCAP:(tbl-[\d-]+|tbl-\d\d-terms)\n:::",
                    lambda m: "::: {#%s}\n%s\n\n%s\n:::" % (m.group(2), m.group(1), captions.get(m.group(2), f"Terms from Session {ch.no}")),
                    md, flags=re.M | re.S)
        chap.append(f"## {name} {{#sec-{ch.nn}-{slugify(name)} .unnumbered}}\n\n{md}\n")
    return "\n".join(chap), "\n".join(key)


# ------------------------------------------------------------------ main
def split_chapters(tex: str) -> tuple[str, str, list[Chapter]]:
    body = tex[tex.index("\\frontmatter"):tex.index("\\end{document}")]
    pre_start = body.index("\\chapter*{Preface}")
    how_start = body.index("\\chapter*{How to use this script}")
    main_start = body.index("\\mainmatter")
    preface = body[pre_start:how_start]
    howto = body[how_start:main_start]
    main = body[main_start:]
    chapters = []
    part = ""
    pieces = re.split(r"^(\\part\{[^}]*\}|\\chapter\{[^}]*\})\n", main, flags=re.M)
    for head, content in zip(pieces[1::2], pieces[2::2]):
        if head.startswith("\\part"):
            part = re.match(r"\\part\{([^}]*)\}", head).group(1)
            continue
        title = re.match(r"\\chapter\{([^}]*)\}", head).group(1)
        no = int(re.search(r"\\label\{ch:(\d+)\}", content).group(1))
        chapters.append(Chapter(no, title, part, content))
    return preface, howto, chapters


def convert_front(preface: str, howto: str) -> None:
    pre = preface.replace("\\chapter*{Preface}\n\\addcontentsline{toc}{chapter}{Preface}", "")
    pre = pandoc(convert_inline_styles(strip_layout(pre)))
    # the answers live in answers/, not in the chapters (instructor decision,
    # as in the other course scripts) - say so where the preface promised them
    pre = pre.replace(
        "ends with the questions we discuss at the end of the session, together with possible answers. The answers are not the only ones; the reasoning behind them is what matters.",
        "ends with the questions we discuss at the end of the session. Possible answers exist, but they are deliberately not printed here: they are not the only ones, and the reasoning behind them is what matters.")
    (ROOT / "index.qmd").write_text(INDEX_HEAD + pre.strip() + "\n" + INDEX_TAIL)
    how = howto.replace("\\chapter*{How to use this script}\n\\addcontentsline{toc}{chapter}{How to use this script}", "")
    how = how.replace("\\tableofcontents", "")
    how = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}",
                 lambda m: "\\begin{tblwrap}\n%s\n\nTBLCAP:tbl-sessions\n\\end{tblwrap}\n" % m.group(0), how, flags=re.S)
    md = pandoc(convert_inline_styles(strip_layout(how)))
    md = re.sub(r"^::: tblwrap\n(.*?)\n\nTBLCAP:tbl-sessions\n:::",
                lambda m: "::: {#tbl-sessions}\n%s\n\nThe twelve sessions, their dates and the reading\n:::" % m.group(1), md, flags=re.M | re.S)
    md = re.sub(r"^## (.+?) \{\.unnumbered\}$", lambda m: f"## {m.group(1)} {{#sec-howto-{slugify(m.group(1))} .unnumbered}}", md, flags=re.M)
    (ROOT / "how-to-use.qmd").write_text("# How to use this script {#sec-how-to-use .unnumbered}\n\n" + md.strip() + "\n")


INDEX_HEAD = """# Preface {.unnumbered}

"""

INDEX_TAIL = """
::: {.callout-tip}
## Annotate this script

You can highlight and annotate any passage of this script with Hypothesis -
select text and comment directly in the margin. See [How to
annotate](appendix/how-to-annotate.qmd) for what counts as a substantive
contribution and how merged contributions are credited.
:::
"""

ANSWER_HEAD = """<!-- Answer key - source-only. answers/ is excluded from every render (see _quarto.yml), so this never appears on the site. -->

# Chapter {no} - sketch answers {{.unnumbered}}

The questions are in `chapters/{nn}-{slug}.qmd`; the sketch answers below are the `\\answer{{}}` texts of the LaTeX script, moved out of the chapter. They are not the only possible answers; the reasoning behind them is what matters.

"""


def write_reading_list(chapters: list[Chapter]) -> None:
    seen = set()
    out = ["# Reading list {#sec-reading-list .unnumbered}", "",
           "This list gathers, in one place, the sources named at the end of each chapter, in the order in which they first appear - the same order as the course's reading folder. A source cited again in a later chapter is listed only once, under the session in which it first appears.", ""]
    for ch in chapters:
        items = []
        for s in ch.sources:
            keym = re.match(r"(.*?\(\d{4}[a-z]?\))", s)
            key = re.sub(r"\s+", " ", keym.group(1) if keym else s).lower()
            key = re.sub(r"\s*---.*$", "", key)
            if key in seen:
                continue
            seen.add(key)
            items.append(pandoc(convert_inline_styles(s)).replace("\n", " "))
        if items:
            out.append(f"## Session {ch.no}: {pandoc_inline(ch.title)} {{.unnumbered}}")
            out.append("")
            out.extend(f"- {i}" for i in items)
            out.append("")
    (ROOT / "appendix" / "reading-list.qmd").write_text("\n".join(out))


def main() -> None:
    tex = SRC.read_text()
    captions = json.loads(CAPTIONS.read_text()) if CAPTIONS.exists() else {}
    preface, howto, chapters = split_chapters(tex)
    convert_front(preface, howto)
    listing = []
    for ch in chapters:
        main = preprocess(ch)
        md = pandoc("\\chapter{%s}\n" % ch.title + main)
        md = postprocess(md, ch, captions)
        tail_md, key_md = render_tail(ch, captions)
        md = md.rstrip() + "\n\n" + tail_md.rstrip() + "\n"
        (ROOT / "chapters" / f"{ch.nn}-{ch.slug}.qmd").write_text(md)
        (ROOT / "answers" / f"{ch.nn}-{ch.slug}.qmd").write_text(
            ANSWER_HEAD.format(no=ch.no, nn=ch.nn, slug=ch.slug) + key_md.rstrip() + "\n")
        for fid, tikz, h in ch.figs:
            (ROOT / "_tikz" / f"{fid}.tikz").write_text(tikz + "\n")
            listing.append((fid, h, captions.get(fid)))
        for tid, h in ch.tbls:
            listing.append((tid, h, captions.get(tid)))
        print(f"    - chapters/{ch.nn}-{ch.slug}.qmd   # part: {ch.part}")
    write_reading_list(chapters)
    if "--list" in sys.argv:
        for k, h, c in listing:
            print(f"{k:14s} | {h[:50]:50s} | {c or '(default)'}")


if __name__ == "__main__":
    main()
