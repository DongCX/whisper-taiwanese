INPUT ?=
OUT ?= outputs
STEM ?=
PRESET ?= tw-mandarin
DEVICE ?= auto
FLAGS ?=

TRANSCRIBE_STEM_ARG := $(if $(STEM),--output-stem "$(STEM)",)

.PHONY: help sync test transcribe
.PHONY: batch

help:
	@printf "%s\n" \
		"make sync" \
		"  Install project dependencies with uv" \
		"" \
		"make test" \
		"  Run unit tests" \
		"" \
		"make transcribe INPUT=/path/to/video.mp4" \
		"  Transcribe one local file with the default tw-mandarin model" \
		"" \
		"make batch INPUT=/path/to/folder" \
		"  Recursively transcribe a directory of local media files" \
		"" \
		"Optional variables for transcribe:" \
		"  OUT=outputs/interview" \
		"  STEM=ep01" \
		"  PRESET=tw-mandarin|nutn-v0.5|balanced" \
		"  DEVICE=cpu|mps|cuda|auto" \
		"  FLAGS='--keep-wav --overwrite'"

sync:
	uv sync --python 3.12

test:
	PYTHONPYCACHEPREFIX=/tmp/whisper-taiwanese-pyc PYTHONPATH=src python3 -m unittest discover -s tests -v

transcribe:
	@test -n "$(INPUT)" || (echo "INPUT is required. Example: make transcribe INPUT=/path/to/video.mp4" >&2; exit 1)
	uv run taiwanese-transcribe "$(INPUT)" --output-dir "$(OUT)" $(TRANSCRIBE_STEM_ARG) --preset "$(PRESET)" --device "$(DEVICE)" $(FLAGS)

batch:
	@test -n "$(INPUT)" || (echo "INPUT is required. Example: make batch INPUT=/path/to/folder" >&2; exit 1)
	uv run taiwanese-transcribe "$(INPUT)" --output-dir "$(OUT)" --preset "$(PRESET)" --device "$(DEVICE)" $(FLAGS)
