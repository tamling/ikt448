# Contributing to the course script

## Environment mapping (LaTeX → Quarto)

How the constructs of `legacy/IKT448_Script.tex` render in this Quarto
book (the mapping is implemented in `tools/tex2qmd.py`):

| LaTeX (legacy/)                 | Quarto (.qmd)                                        | Rendered as                         |
|---------------------------------|------------------------------------------------------|-------------------------------------|
| `\chapter{T}` / `\part{P}`      | `# T {#sec-NN-slug}` / `part:` in `_quarto.yml`      | numbered chapter in a book part     |
| `\section{T}`                   | `## T {#sec-NN-slug}`                                | numbered section                    |
| `\section*{T}` (end sections)   | `## T {#sec-NN-slug .unnumbered}`                    | unnumbered section                  |
| `\sessionhead{N}{…}`            | `::: {.callout-note appearance="simple" icon="false"}` | session line under the title      |
| `\begin{block}{T}`              | `::: {.callout-note}` + `## T`                       | shaded box (definitions, examples)  |
| `\begin{alertblock}{T}`         | `::: {.callout-important}` + `## T`                  | red box (warnings, essay advice)    |
| `\item … \answer{…}` in *Questions …* | `::: {#exr-NN-slug}` + `## T`; answer → `answers/NN-slug.qmd` | numbered Exercise, `@exr-`; answer never rendered |
| `tikzpicture`                   | source in `_tikz/fig-NN-k.tikz`, built to SVG        | `![…](figures/fig-NN-k.svg){#fig-NN-k}` |
| `tabular`                       | pandoc table inside `::: {#tbl-NN-k}` + caption      | numbered, cross-referenced table    |
| `columns`, `minipage`, `center`, `resizebox`, font sizes | dropped                       | sequential content                  |
| `\src{…}`, `{\color{uiagrey}…}` | `*…*`                                                | italic source note                  |
| `$\rightarrow$`, `$\cdot$` …    | `→`, `·` …                                           | plain text                          |

Students and colleagues can become contributors — and, with sustained
substantive contributions, credited co-authors — of this script. Smaller
in-place suggestions go through annotations (see the *How to annotate*
appendix); everything larger goes through this flow.

## Contribution types

- **Glossary entry** — a precise definition (2–5 sentences) of a term used
  in the script, with the chapter/section it belongs to and, if the term is
  contested, the competing usages.
- **Worked example** — a step-by-step example illustrating one concept from
  a chapter, complete enough to follow without the contributor present.
- **Exercise scenario** — an applied scenario with a task statement, the
  chapter sections it exercises, and a model answer for the answer key
  (`answers/`, never shown in the chapter).

Submit as a pull request against the chapter file (plus `answers/` where an
exercise adds self-check material), or — if you don't work with git — as a
document to the course lead, who will turn it into a PR crediting you.
Note that the chapter files are generated from `legacy/IKT448_Script.tex`
by `tools/tex2qmd.py`; a change that should survive the next regeneration
goes into the LaTeX source (or the converter), not only into the `.qmd`.

## Review rubric

Every contribution is reviewed against four criteria; all four must pass:

1. **Technical correctness** — factually and technically accurate;
   verifiable claims are sourced.
2. **Fit** — belongs in the chapter it targets, matches the script's scope
   and level, and doesn't duplicate existing content.
3. **Clarity** — understandable to a fellow student on first reading;
   terminology consistent with the rest of the script.
4. **Sources** — external material is cited, licence-compatible, and not
   copied beyond quotation; examples drawn from real organisations are
   anonymised where appropriate.

The reviewer (course lead) may edit for style and integration. Accepted
contributions are credited in `CHANGELOG.md` (contributor name or chosen
handle + what was merged).

## Licence and contributor statement

By submitting a contribution you confirm that:

- the contribution is your own work (or clearly attributed and
  licence-compatible), and
- you licence it under the script's licence — **placeholder: CC BY-NC-SA
  4.0, pending the institutional decision on the script's final licence** —
  so it can be published, revised, and redistributed as part of the script.

If the institution settles on a different licence, contributors will be
asked to re-confirm before relicensing anything they authored.

> ⚠️ Note: the repository's `LICENSE` file currently contains **GPL-3.0**
> (the default it was created with). It does not yet reflect the intended
> script licence above — replace it once the institutional decision is made.
