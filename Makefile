.PHONY: install-skygrid install-edgesim test-skygrid test-edgesim reproduce-paper

PYTHON ?= python

install-skygrid:
	cd SkyGrid_spark && $(PYTHON) -m pip install -r requirements.txt && $(PYTHON) -m pip install -e .

install-edgesim:
	cd SparkEdgeSim && $(PYTHON) -m pip install -e ".[dev]"

test-skygrid:
	cd SkyGrid_spark && $(PYTHON) -m pytest -q

test-edgesim:
	cd SparkEdgeSim && $(PYTHON) -m pytest -q

# Full paper reproduction (main / multiseed / ablation / scaling / … / figures)
reproduce-paper: install-skygrid
	$(MAKE) -C SkyGrid_spark all
