.PHONY: default venv build install clean

default: install

venv:
	@[ ! -d ./venv ] && python3 -m venv venv && bash -c \
		"source venv/bin/activate && \
		pip install --upgrade pip && \
		pip install -r requirements.txt" || true

build: venv
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "[ERROR]: There are uncommitted changes or untracked files."; \
		exit 1; \
	fi
	@bash -c \
		"source venv/bin/activate && \
		pip install build twine && \
		python -m build"

install: venv
	@bash -c "source venv/bin/activate && pip install -e ."

clean:
	rm -rf venv dist tarc.egg-info
