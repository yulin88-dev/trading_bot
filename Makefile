.PHONY: help install test smoke-data smoke-analysis report run register-help clean monitor-once monitor-dry-run monitor-install monitor-uninstall

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
	@echo ""
	@echo "  v2 monitor:"
	@echo "  make monitor-once       Run mcp_server.monitor once (real eval lands in Prompt 5)"
	@echo "  make monitor-dry-run    Same, with --dry-run"
	@echo "  make monitor-install    launchctl bootstrap the plist (Prompt 5)"
	@echo "  make monitor-uninstall  launchctl bootout the plist (Prompt 5)"

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

PLIST_NAME := com.user.trading-bot-monitor
USER_PLIST_PATH := $(HOME)/Library/LaunchAgents/$(PLIST_NAME).plist
LAUNCHD_DOMAIN := gui/$(shell id -u)

monitor-once:
	$(PYTHON) -m mcp_server.monitor

monitor-dry-run:
	$(PYTHON) -m mcp_server.monitor --dry-run

monitor-install:
	@mkdir -p $(HOME)/Library/LaunchAgents $(HOME)/Library/Logs
	$(PYTHON) scripts/render_plist.py > $(USER_PLIST_PATH)
	-launchctl bootout $(LAUNCHD_DOMAIN)/$(PLIST_NAME) 2>/dev/null || true
	launchctl bootstrap $(LAUNCHD_DOMAIN) $(USER_PLIST_PATH)
	@echo ""
	@echo "Installed: $(USER_PLIST_PATH)"
	@echo "Logs:      $(HOME)/Library/Logs/trading-bot-monitor.log"
	@echo "Status:    launchctl print $(LAUNCHD_DOMAIN)/$(PLIST_NAME)"

monitor-uninstall:
	-launchctl bootout $(LAUNCHD_DOMAIN)/$(PLIST_NAME) 2>/dev/null || true
	rm -f $(USER_PLIST_PATH)
	@echo "Removed: $(USER_PLIST_PATH)"
