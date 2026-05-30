PYTHON_ENVIRONMENT := PYTHONASYNCDEBUG=1 PYTHONDEBUG=1

check: flake8 mypy

format: pyupgrade autoflake isort black 

pyupgrade:
	pyupgrade --exit-zero-even-if-changed --py313-plus $(shell find pyeep tests -name "*.py")

black:
	black pyeep tests

autoflake:
	autoflake --in-place --recursive pyeep tests

isort:
	isort pyeep tests

flake8:
	flake8 pyeep tests

mypy:
	mypy -p pyeep -m tests

unittest:
	$(PYTHON_ENVIRONMENT) pytest

coverage:
	$(PYTHON_ENVIRONMENT) pytest --cov=egtlib --cov-report html 

.PHONY: check pyupgrade black mypy unittest coverage
