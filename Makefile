
venv: clean
	python -m venv venv
	. venv/bin/activate && pip install setuptools wheel twine pytest
	. venv/bin/activate && pip install -e .


.PHONY: build
build: venv
	python setup.py sdist bdist_wheel


.PHONY: tests
tests:
	. venv/bin/activate && pytest


.PHONY: deploy
deploy: build
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then \
		echo "You can only build from the main branch!"; \
		exit 1; \
	fi
	@set -e; twine upload dist/*


.PHONY: clean
clean:
	rm -rf lloam.egg-info
	rm -rf dist
	rm -rf build
	rm -rf venv


