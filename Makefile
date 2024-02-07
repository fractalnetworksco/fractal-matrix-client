.PHONY: test-ci synapse

ENV="fractal_matrix_client.dev.env"
SHELL=/bin/bash

TEST = ""

test-ci:
	docker compose up synapse --build --force-recreate -d --wait
	docker compose up test --build --force-recreate --exit-code-from test
	docker compose down

setup:
	python test-config/prepare-test.py

test:
	. ${ENV} && pytest -k ${TEST} -s --cov-config=.coveragerc --cov=fractal -v --asyncio-mode=auto --cov-report=lcov --cov-report=term tests/

qtest:
	. ${ENV} && pytest -k ${TEST} -s --cov-config=.coveragerc --cov=fractal --asyncio-mode=auto --cov-report=lcov tests/

synapse:
	docker compose -f ./synapse/docker-compose.yml up synapse -d --force-recreate --build
