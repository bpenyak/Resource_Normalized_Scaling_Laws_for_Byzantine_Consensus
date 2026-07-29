# Overleaf upload bundle

Upload this folder (or `overleaf_files.zip` from the repo root) to
[Overleaf](https://www.overleaf.com/) as a new project:
**New Project → Upload Project**.

## Compiler settings

| Setting | Value |
|---|---|
| Compiler | **pdfLaTeX** (not XeLaTeX / LuaLaTeX) |
| Main document | `paper3.tex` |
| BibTeX | not used (manual `thebibliography`) |

Recompile twice if cross-references show as `??`.

## Required structure

```
overleaf_files/
  paper3.tex
  macros.tex
  numbers.tex
  MMC.sty
  latexmkrc
  sections/
    01_introduction.tex
    02_related_work.tex
    03_model.tex
    04_sizing.tex
    05_experiments.tex
    06_case_study.tex
    07_conclusions.tex
  bib/
    references.tex
  figures/
    fig_confounding.pdf
    fig_roc.pdf
    fig_window.pdf
```

Keep relative paths unchanged (`sections/…`, `bib/…`, `figures/…`).

## Notes

- `MMC.sty` needs TeX Live packages already present on Overleaf (`babel`,
  `algorithm`, `xy`, `pb-diagram`, etc.).
- Ukrainian title page comes from `\maketitleUkr` after the references.
- Do not upload `notes/`, `experiments/`, or `data/` — they are not required
  for the PDF.
