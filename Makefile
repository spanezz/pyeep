PYTHON_ENVIRONMENT := PYTHONASYNCDEBUG=1 PYTHONDEBUG=1

check: flake8 mypy

format: pyupgrade autoflake isort black 

pyupgrade:
	pyupgrade --exit-zero-even-if-changed --py313-plus $(shell find pyeep -name "*.py")

black:
	black pyeep

autoflake:
	autoflake --in-place --recursive pyeep

isort:
	isort pyeep

flake8:
	flake8 pyeep

mypy:
	mypy

unittest:
	$(PYTHON_ENVIRONMENT) pytest

coverage:
	$(PYTHON_ENVIRONMENT) pytest --cov=egtlib --cov-report html 

.PHONY: check pyupgrade black mypy unittest coverage
