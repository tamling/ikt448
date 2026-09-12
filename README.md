# IKT448 — course script (Quarto)

Quarto book project for the IKT448 (ICT Research Methods, University of
Agder) course script, converted from the LaTeX lecture script and modelled
on the GRC1100 and SKY2100 course-script repositories.

```
_quarto.yml               project config; annotations flag (ON); answers/ excluded
includes/hypothesis.html  the Hypothesis embed snippet (header include)
includes/interactive.html the sort/order/pick exercise engine (after-body include)
index.qmd                 book landing page (the script's preface)
how-to-use.qmd            sessions, learning outcomes, assessment, the book
chapters/                 one chapter per session (NN-name.qmd) + figures/
chapters/_NN-interactive.qmd  the interactive exercises, included per chapter
legacy/                   the frozen LaTeX script (read-only source)
_tikz/                    TikZ sources for the figures + build.sh → chapters/figures/*.svg
answers/                  per-chapter sketch answers — source-only, never rendered
appendix/                 reading list, how-to-annotate
tools/                    tex2qmd.py (LaTeX → Quarto), make_interactive.py,
                          captions.json, annotation audit trail
theme-light.scss          light theme tweaks (cosmo)
theme-dark.scss           dark theme tweaks (darkly); light backing for figures
```

Render: `quarto render`. Every page carries the **light/dark toggle**
(`format.html.theme` with a `light:`/`dark:` pair in `_quarto.yml`); the
figures are transparent SVGs that get a light backing card in dark mode via
`theme-dark.scss`.

The Hypothesis annotation layer is **on by default** (`annotations: true` +
`include-in-header` in `_quarto.yml`); set the flag to false and remove the
header include to switch it off. Annotations for the course live in the
private Hypothesis group
[IKT 448 2026](https://hypothes.is/groups/XjreopNx/ikt-448-2026) (see the
*How to annotate* appendix and `tools/README.md`).

## Regenerating from the LaTeX script

`legacy/IKT448_Script.tex` is the frozen source. When a new version of the
script arrives, replace that file and run

```sh
python3 tools/make_interactive.py   # chapters/_NN-interactive.qmd
python3 tools/tex2qmd.py            # chapters/, answers/, _tikz/, index, how-to-use, reading list
sh _tikz/build.sh                   # chapters/figures/*.svg (needs pdflatex + pdftocairo)
quarto render
```

`tools/tex2qmd.py --list` prints every figure and table with its caption;
captions live in `tools/captions.json` (an id without an entry falls back to
the heading of the subsection it sits in). Hand edits to the generated
chapter files are overwritten by the next run — put them in the LaTeX
source, the captions file or the converter instead.

## Figures

`_tikz/` holds one `.tikz` source per figure (extracted from the script)
plus `preamble.tex` (UiA colours, TikZ styles). `sh _tikz/build.sh`
rebuilds `chapters/figures/*.svg`; it needs `pdflatex` (with TikZ and
Latin Modern) and `pdftocairo`.

## Questions and answers

Each chapter ends with the script's *Questions from the reading* and
*Questions for discussion* as numbered exercises, followed by the
interactive exercises. The `\answer{}` texts of the LaTeX script were
moved out of the chapters into `answers/NN-name.qmd`, which the render
excludes (`!answers/` in `_quarto.yml`), so answers never appear on the
published site.
