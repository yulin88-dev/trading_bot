"""MCP server entry point — registers tools and runs over stdio."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.logging_setup import log_tool, setup_logging
from mcp_server.tools import analysis_tools, data_tools, report_tools

mcp = FastMCP("trading-bot-mcp")

# Each tool is wrapped with log_tool to capture args, duration, and status.
mcp.tool()(log_tool(data_tools.get_price_history))
mcp.tool()(log_tool(data_tools.get_current_quote))
mcp.tool()(log_tool(data_tools.get_news))

mcp.tool()(log_tool(analysis_tools.compute_weekly_performance))
mcp.tool()(log_tool(analysis_tools.compute_technicals))
mcp.tool()(log_tool(analysis_tools.compute_volatility))
mcp.tool()(log_tool(analysis_tools.compare_to_benchmark))

mcp.tool()(log_tool(report_tools.generate_weekly_report))


def main() -> None:
    setup_logging()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
