.PHONY: help test coverage docs flake8 isort test-full lint
.DEFAULT_GOAL := help


help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo "  test-full  to run test suite and check code coverage"
	@echo "  lint       to run flake8 and isort"
	@echo "  test       to run test suite"
	@echo "  coverage   to check code coverage"
	@echo "  flake8     to check code linting"
	@echo "  isort      to check import ordering"
	@echo "  docs       to generate documentation"


test:
	py.test


coverage:
	py.test --cov-report xml --cov-report html --cov tg_option_container


flake8:
	flake8 tg_option_container tests

docs:
	cd docs && make html

isort:
	isort --recursive --check-only -p tests tg_option_container tests --diff


test-full: coverage
lint: coverage flake8 isort
