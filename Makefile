# Reproducible pipeline for the NYC Subway bullet fonts and LaTeX package.
#
#   make download   fetch SVGs from Wikimedia Commons (skips files we have)
#   make mappings   add new files to data/mappings/*.tsv (keeps your edits)
#   make fonts      build fonts/NYCSubwayBullets-*.ttf
#   make specimens  write specimens/index.html for checking in a browser
#   make latex      generate the LaTeX data files and copy the fonts
#   make doc        typeset latex/nycbullets.pdf
#   make check      run the Python tests and the l3build tests
#   make ctan       build the CTAN archive latex/nycbullets-ctan.zip
#   make install    install the package into your TEXMFHOME
#   make all        download, mappings, fonts, specimens, latex, doc
#
# See docs/PIPELINE.md for details.

UV      ?= uv
RUN     := $(UV) run nycbullets
L3BUILD ?= l3build

.PHONY: all download mappings fonts specimens latex doc check ctan install clean

all: download mappings fonts specimens doc

download:
	$(RUN) download

mappings:
	$(RUN) map

fonts:
	$(RUN) build

specimens:
	$(RUN) specimen

latex:
	$(RUN) tex

doc: latex
	cd latex && $(L3BUILD) doc
	cp latex/nycbullets.pdf docs/nycbullets.pdf

check: latex
	$(UV) run pytest
	cd latex && $(L3BUILD) check

ctan: latex
	cd latex && $(L3BUILD) ctan

install: latex
	cd latex && $(L3BUILD) install

clean:
	cd latex && $(L3BUILD) clean
	rm -rf specimens
