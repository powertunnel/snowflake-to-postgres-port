"""MCP server — the analog of the Snowflake managed MCP server.

Exposes the warehouse's two capabilities as MCP tools so any MCP client
(Claude Code, Claude Desktop, CoCo, custom apps) can discover and call them.
The connecting client's model does the orchestration/routing — exactly the role
the Cortex Agent plays in the Snowflake version.

Run (stdio):  python -m aiagent.mcp_server
Register with Claude Code, e.g.:
  claude mcp add snowport-analytics -- \
      /home/sandbox/snow/.dbt-venv/bin/python -m aiagent.mcp_server
"""
from mcp.server.mcpserver import MCPServer
from . import tools, config

server = MCPServer(
    name="snowport-analytics",
    instructions=(
        "Retail snow-sports analytics over a PostgreSQL warehouse. "
        "Use query_business_data for quantitative/structured questions (revenue, "
        "orders, customers, products) and search_customer_feedback for qualitative "
        "'why' questions over reviews and support tickets."
    ),
)


@server.tool(
    name="query_business_data",
    title="Business Data (text-to-SQL)",
    description=("Answer quantitative questions about orders, revenue, customers and "
                 "products. Generates read-only PostgreSQL from a semantic model and "
                 "runs it. Returns the SQL, columns and rows."),
)
def query_business_data(question: str, role: str = None) -> dict:
    """question: natural-language analytical question.
    role: 'analyst_ro' (all data) or 'west_coast_manager' (RLS-filtered)."""
    return tools.query_business_data(question, role=role or config.DEFAULT_ROLE)


@server.tool(
    name="count_feedback_mentions",
    title="Count Feedback Mentions",
    description=("Accurate counts and breakdowns of reviews/tickets mentioning terms "
                 "(scans all matching rows). Use for 'how many mention X' and 'which "
                 "products are most affected' — not the capped search tool."),
)
def count_feedback_mentions(terms: str, source: str = "reviews",
                            group_by: str = "none", role: str = None) -> dict:
    """terms: space-separated, OR'd. source: reviews|tickets|all.
    group_by: reviews none|product|rating; tickets none|category|priority|status."""
    return tools.count_feedback_mentions(terms, source=source, group_by=group_by,
                                         role=role or config.DEFAULT_ROLE)


@server.tool(
    name="search_customer_feedback",
    title="Customer Feedback Search",
    description=("Full-text search across product reviews and support tickets. "
                 "Use for complaint themes, 'reviews mentioning X', returns, sizing, etc."),
)
def search_customer_feedback(query: str, source: str = "all",
                             filters: dict = None, role: str = None) -> dict:
    """query: search terms. source: reviews|tickets|all.
    filters: {max_rating, product_id, category, priority}."""
    return tools.search_customer_feedback(query, source=source, filters=filters,
                                          role=role or config.DEFAULT_ROLE)


def main():
    server.run("stdio")


if __name__ == "__main__":
    main()
