"""MCP server entry point — registers v1 + v2 tools and runs over stdio."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.alerts import store as alerts_store
from mcp_server.logging_setup import log_tool, setup_logging
from mcp_server.tools import (
    alert_tools,
    analysis_tools,
    data_tools,
    notifier_tools,
    report_tools,
)

mcp = FastMCP("trading-bot-mcp")

# Each tool is wrapped with log_tool to capture args, duration, and status.

# v1 — Data tools
mcp.tool()(log_tool(data_tools.get_price_history))
mcp.tool()(log_tool(data_tools.get_current_quote))
mcp.tool()(log_tool(data_tools.get_news))

# v1 — Analysis tools
mcp.tool()(log_tool(analysis_tools.compute_weekly_performance))
mcp.tool()(log_tool(analysis_tools.compute_technicals))
mcp.tool()(log_tool(analysis_tools.compute_volatility))
mcp.tool()(log_tool(analysis_tools.compare_to_benchmark))

# v1 — Report tool
mcp.tool()(log_tool(report_tools.generate_weekly_report))

# v2 — Alert CRUD
mcp.tool()(log_tool(alert_tools.add_alert))
mcp.tool()(log_tool(alert_tools.update_alert))
mcp.tool()(log_tool(alert_tools.list_alerts))
mcp.tool()(log_tool(alert_tools.get_alert))
mcp.tool()(log_tool(alert_tools.pause_alert))
mcp.tool()(log_tool(alert_tools.resume_alert))
mcp.tool()(log_tool(alert_tools.delete_alert))
mcp.tool()(log_tool(alert_tools.get_alert_history))

# v2 — Evaluation
mcp.tool()(log_tool(alert_tools.evaluate_alerts))

# v2 — Notification
mcp.tool()(log_tool(notifier_tools.send_test_email))


def main() -> None:
    setup_logging()
    alerts_store.ensure_initialized()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
