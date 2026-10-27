"""MCP stdio server: exposes read-only provider search as a tool."""
import asyncio
from mcp.server.fastmcp import FastMCP
from app.services.directory import search_directory

mcp = FastMCP("NHS CareFinder service search")

@mcp.tool()
async def find_nhs_services(service: str, postcode: str, limit: int = 10) -> list[dict]:
    """Search public NHS service directory records. Not appointment availability or diagnosis."""
    limit = max(1, min(int(limit), 20))
    results = await search_directory(service[:100], postcode[:10], limit)
    return [item.model_dump() for item in results]

if __name__ == "__main__":
    mcp.run(transport="stdio")
