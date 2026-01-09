from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from datetime import datetime
import pytz # 需要 pip install pytz

# 创建一个名为 "geo-time-server" 的 MCP 服务
mcp = FastMCP("geo-time-server")

@mcp.tool()
async def get_location_and_time(ip_address: str) -> str:
    """
    根据 IP 地址获取地理位置、时区和当前的本地时间。
    返回 JSON 字符串。
    """
    # 1. 使用 ip-api.com 获取位置和时区 (免费版，非商业用途)
    url = f"http://ip-api.com/json/{ip_address}"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        data = resp.json()

    if data.get("status") != "success":
        return f"Error: Could not retrieve data for IP {ip_address}"

    timezone_str = data.get("timezone", "UTC")
    city = data.get("city", "Unknown")
    country = data.get("country", "Unknown")
    
    # 2. 根据时区计算当前时间
    try:
        tz = pytz.timezone(timezone_str)
        local_time = datetime.now(tz).isoformat()
    except Exception:
        local_time = datetime.now().isoformat()

    return {
        "ip": ip_address,
        "location": f"{city}, {country}",
        "timezone": timezone_str,
        "current_local_time": local_time
    }

if __name__ == "__main__":
    mcp.run()