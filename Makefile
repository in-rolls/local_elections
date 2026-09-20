PY ?= uv run python
# The Apple-Silicon model stack stays out of parser-only environments.
OCR_PY ?= uv run --no-default-groups --group ocr python
TABLE_OCR_PY ?= uv run --group table-ocr python
UV_DOCKER_IMAGE ?= ghcr.io/astral-sh/uv:0.12.7-python3.12-trixie

.PHONY: help inventory probe assam assam-2025 assam-2025-extract assam-2025-ocr assam-harvest gujarat gujarat-ocr gujarat-harvest gujarat-validate goa jharkhand jharkhand-ocr jharkhand-bench jharkhand-bench-record jk jk-2010-extract jk-2016-extract ap karnataka maharashtra maharashtra-harvest telangana wb validate test ci-docker coverage state-readmes stats worklist master manifest verify release-check expect dictionary

help:
	@echo "make inventory   classify the source documents already in data/"
	@echo "make probe       fetch candidate web sources and classify them"
	@echo "make assam      parse + validate held Assam reservation sources"
	@echo "make assam-2025 parse + validate held Assam 2025 PRI sources"
	@echo "make assam-2025-extract  extract reviewed Assam 2025 source tables"
	@echo "make assam-2025-ocr DISTRICT=...  OCR one Assam district scan"
	@echo "make assam-harvest  fetch Assam's 2025 district PRI notifications"
	@echo "make gujarat     parse + validate held Gujarat rotation orders"
	@echo "make gujarat-ocr extract raw cells from Gujarat's encoded PDFs"
	@echo "make gujarat-harvest  fetch Gujarat's 2020 PRI rotation orders"
	@echo "make gujarat-validate verify Gujarat's held sources offline"
	@echo "make goa         parse + validate Goa ward reservation"
	@echo "make jharkhand   parse + validate Jharkhand, one file per tier"
	@echo "make jharkhand-ocr  re-read the Jharkhand scans with Surya (~6h)"
	@echo "make jharkhand-bench  gates for a Jharkhand parser change"
	@echo "make jk          parse + validate Jammu & Kashmir"
	@echo "make jk-2010-extract  extract J&K 2010 digital tables"
	@echo "make jk-2016-extract  extract J&K 2016 digital tables"
	@echo "make ap          parse + validate Andhra Pradesh"
	@echo "make karnataka   parse + validate Karnataka's held source series"
	@echo "make maharashtra parse + validate Mumbai (BMC) ward seats"
	@echo "make maharashtra-harvest  fetch the Karekurve-Ramachandra & Lee Dataverse deposit"
	@echo "make telangana   parse + validate Telangana"
	@echo "make wb          parse + validate West Bengal"
	@echo "make validate    run every state validator without reparsing"
	@echo "make coverage    regenerate the readme table and check every link"
	@echo "make expect      triage every column against the data dictionary"
	@echo "make dictionary  regenerate DICTIONARY.md from the declarations"
	@echo "make test        unit tests for the shared normalizer"
	@echo "make ci-docker   run the release checks in a clean Python 3.12 container"
	@echo "make sweep       what the web archive holds, per state commission"
	@echo "make karnataka-ocr  read the Kannada scans; resumable, ~10 hours"
	@echo "make transliterate  Indic names -> Latin, into a committed table"
	@echo "make sources        rebuild SOURCES.md's holdings table from disk"

inventory:
	$(PY) -m local_reservations.tools.inventory

probe:
	$(PY) -m local_reservations.tools.probe_sources --skip-unreachable

assam: assam-2025-extract
	$(PY) -m local_reservations.states.assam.parse
	$(PY) -m local_reservations.states.assam.parse_2025
	$(PY) -m local_reservations.states.assam.validate

assam-harvest:
	$(PY) -m local_reservations.states.assam.harvest

assam-2025-extract:
	$(PY) -m local_reservations.states.assam.extract_2025

assam-2025-ocr:
	$(OCR_PY) -m local_reservations.states.assam.ocr_2025 --district "$(DISTRICT)"

assam-2025: assam-2025-extract
	$(PY) -m local_reservations.states.assam.parse_2025
	$(PY) -m local_reservations.states.assam.validate

gujarat-harvest:
	$(PY) -m local_reservations.states.gujarat.harvest

gujarat-ocr:
	$(PY) -m local_reservations.states.gujarat.ocr

gujarat:
	$(PY) -m local_reservations.states.gujarat.parse
	$(PY) -m local_reservations.states.gujarat.validate

gujarat-validate:
	$(PY) -m local_reservations.states.gujarat.validate

sweep:
	$(PY) -m local_reservations.tools.archive_sweep

# Both resume. The OCR skips documents it has already cached and, within a
# document, pages it has already read; the harvest skips files whose bytes on
# disk still hash to what the manifest recorded. Re-running either is how you
# resume it - there is no separate command and no state to clean up.
# The third stage: collect -> parse -> transliterate -> pool. Writes a lookup
# table keyed on the name, which is committed; the pooled build only reads it.
# --with indicate rather than a dependency group: it pulls torch and is needed
# only when the table is regenerated, which is rarely.
transliterate:
	uv run --with indicate python -m local_reservations.tools.transliterate

karnataka-ocr:
	$(OCR_PY) -m local_reservations.states.karnataka.ocr

goa:
	$(PY) -m local_reservations.states.goa.parse
	$(PY) -m local_reservations.states.goa.validate

jharkhand:
	$(PY) -m local_reservations.states.jharkhand.parse
	$(PY) -m local_reservations.states.jharkhand.validate

# The gates a parser change has to clear, against data/stats/jharkhand_bench.json.
# `make jharkhand-bench-record` stores what the code does now; run it only when
# you have decided the current numbers are the ones to defend.
jharkhand-bench:
	$(PY) -m local_reservations.states.jharkhand.bench

jharkhand-bench-record:
	$(PY) -m local_reservations.states.jharkhand.bench --record

# Not part of `make jharkhand`, and not a dependency of anything. Its output is
# committed, it takes about six hours, and it needs an interpreter the rest of
# the repository cannot share, so uv runs it from the isolated OCR group.
jharkhand-ocr:
	$(OCR_PY) -m local_reservations.states.jharkhand.ocr
	$(PY) -m local_reservations.states.jharkhand.ocr_seats

jk-2010-extract:
	$(PY) -m local_reservations.states.jk.extract_2010

jk-2016-extract:
	$(PY) -m local_reservations.states.jk.extract_2016

jk: jk-2010-extract jk-2016-extract
	$(PY) -m local_reservations.states.jk.parse
	$(PY) -m local_reservations.states.jk.validate

ap:
	$(PY) -m local_reservations.states.ap.parse
	$(PY) -m local_reservations.states.ap.validate

karnataka:
	$(PY) -m local_reservations.states.karnataka.parse
	$(PY) -m local_reservations.states.karnataka.parse_tzp
	$(PY) -m local_reservations.states.karnataka.validate

maharashtra:
	$(PY) -m local_reservations.states.maharashtra.parse
	$(PY) -m local_reservations.states.maharashtra.validate

maharashtra-harvest:
	$(PY) -m local_reservations.states.maharashtra.harvest

telangana:
	$(PY) -m local_reservations.states.telangana.parse
	$(PY) -m local_reservations.states.telangana.validate

wb:
	$(PY) -m local_reservations.states.wb.parse
	$(PY) -m local_reservations.states.wb.validate

.PHONY: wb-gp-extract wb-gp-parse wb-gp-validate wb-gp-reservations
wb-gp-reservations:
	$(PY) -m local_reservations.states.wb.parse_birbhum
	$(PY) -m local_reservations.states.wb.reservation_coverage

wb-gp-extract:
	$(PY) -m local_reservations.states.wb.extract_native
	$(TABLE_OCR_PY) -m local_reservations.states.wb.extract_results

wb-gp-parse:
	$(PY) -m local_reservations.states.wb.parse_hooghly
	$(PY) -m local_reservations.states.wb.parse_nadia
	$(PY) -m local_reservations.states.wb.parse_results

wb-gp-validate:
	$(PY) -m local_reservations.states.wb.validate_gp

.PHONY: wb-parse-all wb-ocr-all wb-parsing-inventory
wb-parse-all:
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_base_drafts
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_birbhum
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_hooghly
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_nadia
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_nadia_handbook
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_alipurduar_offices
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_office_native --workers 2
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_office_scans --workers 2
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_ward_schedules
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_ancillary
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_reference_tables
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parse_results
	$(TABLE_OCR_PY) -m local_reservations.states.wb.validate_gp
	$(TABLE_OCR_PY) -m local_reservations.states.wb.reservation_coverage
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parsing_inventory

wb-ocr-all:
	OMP_THREAD_LIMIT=1 $(TABLE_OCR_PY) -m local_reservations.states.wb.parse_ward_schedules --ocr --workers 2
	OMP_THREAD_LIMIT=1 $(TABLE_OCR_PY) -m local_reservations.states.wb.parse_ancillary --ocr
	OMP_THREAD_LIMIT=1 $(TABLE_OCR_PY) -m local_reservations.states.wb.parse_reference_tables --ocr --workers 1
	$(MAKE) wb-parse-all

wb-parsing-inventory:
	$(TABLE_OCR_PY) -m local_reservations.states.wb.parsing_inventory

validate:
	$(PY) -m local_reservations.states.ap.validate
	$(PY) -m local_reservations.states.assam.validate
	$(PY) -m local_reservations.states.goa.validate
	$(PY) -m local_reservations.states.gujarat.validate
	$(PY) -m local_reservations.states.jharkhand.validate
	$(PY) -m local_reservations.states.jk.validate
	$(PY) -m local_reservations.states.karnataka.validate
	$(PY) -m local_reservations.states.maharashtra.validate
	$(PY) -m local_reservations.states.telangana.validate
	$(PY) -m local_reservations.states.wb.validate

master:
	$(PY) -m local_reservations.tools.build_master

manifest:
	$(PY) -m local_reservations.tools.build_manifest

verify:
	$(PY) -m local_reservations.tools.verify_manifest

.PHONY: tn evidence evidence-archives verify-evidence verify-evidence-archives
tn:
	$(PY) -m local_reservations.states.tn.parse_heads_2011
	$(PY) -m local_reservations.states.tn.parse_amendments_2001

evidence:
	$(PY) -m local_reservations.tools.build_evidence

evidence-archives:
	$(PY) -m local_reservations.tools.build_evidence --archive-dir "$(CURDIR)/dist/source-evidence"
	$(PY) -m local_reservations.tools.verify_manifest --manifest SOURCE_MANIFEST.json
	$(PY) -m local_reservations.tools.verify_manifest --manifest SOURCE_MANIFEST.json --archives "$(CURDIR)/dist/source-evidence"

verify-evidence:
	$(PY) -m local_reservations.tools.verify_manifest --manifest SOURCE_MANIFEST.json

verify-evidence-archives:
	$(PY) -m local_reservations.tools.verify_manifest --manifest SOURCE_MANIFEST.json --archives "$(CURDIR)/dist/source-evidence"

# Prepares and checks a release. It deliberately does not tag: a tag is one of
# the few things you cannot take back, so this prints the command and a human
# runs it.
release-check: test validate master stats worklist coverage manifest verify verify-evidence verify-evidence-archives
	@$(PY) -m local_reservations.tools.release_check $(VERSION)

stats:
	$(PY) -m local_reservations.tools.build_stats --quiet

worklist:
	$(PY) -m local_reservations.tools.build_worklist

coverage: stats worklist state-readmes sources
	$(PY) -m local_reservations.tools.build_coverage --check

# SOURCES.md is a feasibility survey and most of it is judgement, which stays
# hand-written. Its holdings table is not: it is a count of what is on disk,
# and it drifted to "1 scan, 7 pages" for a state holding 649 documents.
sources:
	$(PY) -m local_reservations.tools.build_sources

state-readmes:
	$(PY) -m local_reservations.tools.build_state_readmes

expect:
	$(PY) -m local_reservations.common.expectations

dictionary:
	$(PY) -m local_reservations.common.make_dictionary

test:
	$(PY) -m pytest tests -q

ci-docker:
	docker run --rm --pull=always \
		--mount type=bind,source="$(CURDIR)",target=/workspace \
		--workdir /workspace \
		--env UV_PROJECT_ENVIRONMENT=/tmp/local-reservations-venv \
		--env UV_CACHE_DIR=/tmp/uv-cache \
		--env RUFF_CACHE_DIR=/tmp/ruff-cache \
		$(UV_DOCKER_IMAGE) \
		sh -c 'apt-get update && \
			apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-ben libgl1 && \
			uv sync --no-default-groups --frozen --group dev --all-extras && \
			uv run ruff check . && \
			uv run ruff format --check . && \
			uv run pyright && \
			uvx --from pydoclint==0.9.1 pydoclint src/ && \
			uvx preen check --strict --skip tests && \
			uv run pytest tests -q -p no:cacheprovider && \
			uv build --out-dir /tmp/dist'

.PHONY: delhi delhi-harvest
delhi-harvest:
	$(PY) -m local_reservations.states.delhi.harvest --root data/delhi/qualification_audit

delhi:
	$(PY) -m local_reservations.states.delhi.parse --root data/delhi/qualification_audit --gazette data/delhi/delhi_2022.pdf
	$(PY) -m local_reservations.states.delhi.validate --release data/delhi/release

.PHONY: audit
audit:
	mkdir -p dist
	uv export --frozen --no-default-groups --group dev --all-extras --no-emit-project --format requirements-txt --output-file dist/audit-requirements.txt > /dev/null
	uvx pip-audit==2.10.1 --require-hashes --disable-pip -r dist/audit-requirements.txt
