from dotenv import load_dotenv
import requests
import os
import json
from fastmcp import FastMCP
import logging
from typing import Any, Dict, List, Optional
from sources import StockNews
from sources import BitcoinNews
from sources import PaymentRequiredException

# Optional import for Web3News if it exists
try:
    from sources import Web3News
except ImportError:
    Web3News = None


logger = logging.getLogger(__name__)
mcp = FastMCP()
load_dotenv()



@mcp.tool()
def get_web3_news(
    query: Optional[str] = None,
    topics: Optional[str] = None
) -> str:
    """
    Search for web3 news articles from Alpha Vantage.
    """
    return "This is a test news tool"

@mcp.tool()
def get_bitcoin_news(
    query: Optional[str] = None,
    topics: Optional[str] = None,
    auth_token: Optional[str] = None
) -> str:
    """
    Search for bitcoin news articles from bitserver.
    
    Args:
        query: Optional search query description (for context)
        topics: Optional topics filter
        auth_token: Optional authorization token (transaction hash) for paid content
    
    Returns:
        Formatted string containing news articles, or JSON string with payment data if 402
    """
    try:
        bitcoin_news = BitcoinNews()
        news = bitcoin_news.retrive_news(auth_token=auth_token)
        
        if not news:
            return "No bitcoin news articles found for the given criteria."
        
        # Format the news articles
        result = f"Found {len(news)} bitcoin news articles:\n\n"
        for i, article in enumerate(news, 1):
            title = article.get("title", "No title")
            summary = article.get("summary", "No summary available")
            url = article.get("url", "")
            source = article.get("source", "Unknown")
            time_published = article.get("time_published", "")
            
            result += f"{i}. {title}\n"
            result += f"   Source: {source}\n"
            if time_published:
                result += f"   Published: {time_published}\n"
            result += f"   Summary: {summary}\n"
            if url:
                result += f"   URL: {url}\n"
            result += "\n"
        
        return result
    except PaymentRequiredException as e:
        # Return payment data as JSON string that can be detected
        # Include the URL so we can retry after payment
        payment_response = {
            "__402_payment_required__": True,
            "payment_data": e.payment_data,
            "source": "bitserver",
            "url": bitcoin_news.base_url  # Include URL for retry
        }
        return json.dumps(payment_response, ensure_ascii=False)
    except Exception as e:
        return f"Error fetching bitcoin news: {str(e)}"

@mcp.tool()
def get_market_news(
    query: Optional[str] = None,
    tickers: Optional[str] = None,
    topics: Optional[str] = None
) -> str:
    """
    Search for market news articles from Alpha Vantage.

    Args:
        query: Optional search query description (for context, not used in API call)
        tickers: Stock/crypto/forex symbols (e.g., "AAPL" or "COIN,CRYPTO:BTC,FOREX:USD")
        topics: News topics (e.g., "technology" or "technology,ipo")

    Returns:
        Formatted string containing news articles with titles, summaries, and URLs
    """
    try:
        retrive_news = StockNews()
        news = retrive_news.retrive_news(tickers=tickers, topics=topics)

        if not news:
            return "No news articles found for the given criteria."

        # Format the news articles
        result = f"Found {len(news)} news articles:\n\n"
        for i, article in enumerate(news, 1):
            title = article.get("title", "No title")
            summary = article.get("summary", "No summary available")
            url = article.get("url", "")
            source = article.get("source", "Unknown")
            time_published = article.get("time_published", "")

            result += f"{i}. {title}\n"
            result += f"   Source: {source}\n"
            if time_published:
                result += f"   Published: {time_published}\n"
            result += f"   Summary: {summary}\n"
            if url:
                result += f"   URL: {url}\n"
            result += "\n"

        return result
    except Exception as e:
        return f"Error fetching news: {str(e)}"


if __name__ == "__main__":
    # 打印当前 CWD 和 PYTHONPATH 帮助 debug
    import sys
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Python Path: {sys.path}")

    port = int(os.getenv("SEARCH_HTTP_PORT", "8001"))
    print(f"Try Running Alpha Vantage News Tool as search tool on port {port}")
    
    try:
        # 建议换个端口试试，比如 8011，看是否还报错
        mcp.run(transport="streamable-http", port=port)
    except Exception as e:
        print(f"Fatal error: {e}")

