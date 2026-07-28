# Makefile -- reproduction pipeline for paper_3
#
#   make smoke    one tiny run, verifies the toolchain
#   make analyze  raw measurements -> numbers.tex + figures
#   make paper    pdflatex twice
#   make all      analyze + paper

PY      ?= python
RAW     ?= data/raw
PROC    ?= data/processed
FIGS    ?= figures
EXP     ?= experiments

.PHONY: all smoke analyze fit pi sizing simulate figures numbers paper clean

all: analyze paper

smoke:
	$(PY) $(EXP)/run_one.py --n 4 --q 0.25 --c 4 --duration 90 \
	    --out $(RAW)/smoke.json

analyze: fit pi sizing figures numbers

fit:
	$(PY) $(EXP)/analysis/fit_bifactor.py --in $(RAW) --out $(PROC)

pi: fit
	$(PY) $(EXP)/analysis/bootstrap_pi.py --in $(PROC) --out $(PROC)

sizing: pi
	$(PY) $(EXP)/analysis/sizing.py --in $(PROC) --out $(PROC)

simulate:
	$(PY) $(EXP)/analysis/simulate.py --in $(PROC) --out $(PROC)

figures: sizing
	$(PY) $(EXP)/analysis/make_figures.py --in $(PROC) --out $(FIGS)

numbers: sizing
	$(PY) $(EXP)/analysis/emit_numbers_tex.py --in $(PROC) --out numbers.tex

paper:
	pdflatex -interaction=nonstopmode paper3.tex
	pdflatex -interaction=nonstopmode paper3.tex

clean:
	rm -f *.aux *.log *.out *.toc *.bbl *.blg paper3.pdf
