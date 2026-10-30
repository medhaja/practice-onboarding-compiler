PYTHON ?= python

.PHONY: install demo eval test data

install:
	$(PYTHON) -m pip install -q -r requirements.txt

demo: install
	$(PYTHON) -m onboarding.app

eval:
	$(PYTHON) -m onboarding.eval

test:
	$(PYTHON) -m pytest -q

data:
	$(PYTHON) -m onboarding.generator
