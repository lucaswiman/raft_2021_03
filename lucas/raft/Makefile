.PHONY: lint
lint:
	black -l 100 *.py
	flake8 --max-line-length=100 --ignore=E203,E401,E266,W503 *.py
	mypy *.py


.PHONY: test
test:
	pytest --cov=. --cov-branch --cov-report=term-missing -vv $(TEST)
