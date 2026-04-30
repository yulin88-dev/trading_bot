"""MCP server entry point — registers tool stubs and runs over stdio."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import analysis_tools, data_tools, report_tools

mcp = FastMCP("trading-bot-mcp")

# Data tools
mcp.tool()(data_tools.get_price_history)
mcp.tool()(data_tools.get_current_quote)
mcp.tool()(data_tools.get_news)

# Analysis tools
mcp.tool()(analysis_tools.compute_weekly_performance)
mcp.tool()(analysis_tools.compute_technicals)
mcp.tool()(analysis_tools.compute_volatility)
mcp.tool()(analysis_tools.compare_to_benchmark)

# Report tool
mcp.tool()(report_tools.generate_weekly_report)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
