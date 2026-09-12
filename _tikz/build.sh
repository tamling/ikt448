#!/bin/sh
# Rebuild the chapter figures from their TikZ sources.
# Requires: pdflatex with TikZ (texlive-pictures, standalone class from
# texlive-latex-extra) and pdftocairo (poppler-utils).
# Output goes to chapters/figures/<name>.svg.
set -e
cd "$(dirname "$0")"
for f in fig-*.tikz; do
  n="${f%.tikz}"
  { cat preamble.tex; cat "$f"; printf '\\end{document}\n'; } > "/tmp/$n.tex"
  pdflatex -interaction=batchmode -halt-on-error -output-directory /tmp "/tmp/$n.tex" >/dev/null
  pdftocairo -svg "/tmp/$n.pdf" "../chapters/figures/$n.svg"
  # 4x the display size (the viewBox stays, so it scales losslessly);
  # wide figures are capped at column width by the site CSS
  python3 - "../chapters/figures/$n.svg" <<'PY'
import re, sys
p = sys.argv[1]
t = open(p).read()
def double(m): return f'{m.group(1)}="{float(m.group(2))*4:g}{m.group(3) or ""}"'
def svgrepl(m): return re.sub(r'\b(width|height)="([0-9.]+)(pt)?"', double, m.group(0))
open(p, 'w').write(re.sub(r'<svg\b[^>]*>', svgrepl, t, count=1))
PY
  echo "built $n.svg"
done
