.PHONY: help install test smoke-data smoke-analysis report run register-help clean

PYTHON := python3

help:
	@echo "Trading Bot MCP — make targets"
	@echo ""
	@echo "  make install          Install package + dev deps in editable mode"
	@echo "  make test             Run unit tests"
	@echo "  make smoke-data       End-to-end smoke test of data tools"
	@echo "  make smoke-analysis   End-to-end smoke test of analysis tools"
	@echo "  make report           Generate this week's market report"
	@echo "  make run              Launch the MCP server (stdio; for debugging)"
	@echo "  make register-help    Print Claude Desktop config block to paste"
	@echo "  make clean            Remove caches and the reports/ directory"

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v

smoke-data:
	$(PYTHON) scripts/smoke_test_data.py

smoke-analysis:
	$(PYTHON) scripts/smoke_test_analysis.py

report:
	$(PYTHON) -c "from mcp_server.tools.report_tools import generate_weekly_report; import json; print(json.dumps(generate_weekly_report(), indent=2))"

run:
	$(PYTHON) -m mcp_server.server

register-help:
	@$(PYTHON) scripts/print_claude_config.py

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__ reports
