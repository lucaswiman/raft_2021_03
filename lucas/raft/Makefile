.PHONY: lint
lint:
	black -l 100 *.py
	flake8 --max-line-length=100 --ignore=E203 *.py
	mypy *.py


.PHONY: test
test:
	pytest -vv $(TEST)
