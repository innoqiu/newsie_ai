import asyncio
import json
import os
from typing import Any, Dict, List, Optional


from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

# MCP & Model Imports
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

# Import accountant agent for payment handling
from agents.accountant import run_accountant_service

load_dotenv()


class NewsRetrievalAgent:
    """
    Agent for retrieving news based on context using MCP tools.
    """
    
    def __init__(self, context: str):
        """
        Initialize the news retrieval agent.
        """
        self.context = context
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.7
        )
        # self.mcp_client: Optional[MultiServerMCPClient] = None
        self.mcp_client = None
        self.agent_runnable = None # Renamed from agent_executor
        
    async def setup_mcp_client(self):
        """Setup MCP client connection to the retrieval tools"""
        mcp_servers = {
            "retrieval_tools": {
                "url": f"http://localhost:{os.getenv('SEARCH_HTTP_PORT', '8001')}/mcp",
                "transport": "streamable-http"
            }
        }
        
        self.mcp_client = MultiServerMCPClient(mcp_servers)
        
    async def create_news_agent(self):
        """Create the LangGraph agent with MCP tools"""
        if not self.mcp_client:
            await self.setup_mcp_client()
        
        # Get tools from MCP client
        tools = await self.mcp_client.get_tools()
        
        # Create the system prompt
        # Note: In LangGraph, we pass this as 'state_modifier' or 'messages_modifier'
        system_prompt = """You are a helpful news retrieval assistant. Your task is to search for relevant news articles based on the context provided by the user.

Instructions:
1. Analyze the context provided by the user to understand what news they are looking for
2. Use the get_market_news tool to search for related news articles
3. You can search by:
   - Stock tickers (e.g., "AAPL", "TSLA", "MSFT")
   - Topics (e.g., "technology", "finance", "earnings")
   - Or a combination of both
4. Review the search results and provide a summary of the most relevant news
5. If you need to search multiple times with different parameters, do so.

Important: When you have provided the summary, just stop naturally. You do not need to output specific tags like tag{Finished}.

CRITICAL EXCEPTION HANDLING:
If the tool returns a JSON string containing "__402_payment_required__", YOU MUST STOP IMMEDIATELY.
Do not summarize it. Do not apologize. Do not add any text.
Your final response must be ONLY the exact JSON string returned by the tool.

"""
        
        # --- FIXED: Use LangGraph Prebuilt Agent ---
        # This replaces the old create_react_agent + AgentExecutor pattern
        self.agent_runnable = create_agent(
            self.llm, 
            tools, 
            system_prompt=system_prompt
        )
        
    async def run(self, user_profile: Optional[Dict[str, Any]] = None) -> str:
        """
        Run the agent with the provided context.
        
        Args:
            user_profile: Optional user profile for payment decisions if 402 is encountered
        """
        if not self.agent_runnable:
            await self.create_news_agent()
        
        # Create the input message with context
        user_input = f"""Based on the following context, search for related news articles:

                        Context: {self.context}

                        Please search for relevant news and provide a summary."""
        
        # --- FIXED: Run the Graph ---
        # LangGraph takes a dictionary with "messages" key
        inputs = {"messages": [HumanMessage(content=user_input)]}
        
        # ainvoke returns the final state of the graph
        result = await self.agent_runnable.ainvoke(inputs)
        agent_response = result["messages"][-1].content
        
        print(f"DEBUG: Raw Agent Response: {agent_response}")

        payment_info = agent_response.strip()
        

        # 1) 先把 response 归一化成 dict
        # if isinstance(agent_response, dict):
        #     data = agent_response
        # elif isinstance(agent_response, str):
        #     s = agent_response.strip()
        #     while s.endswith("}}"):
        #         s = s[:-1]
        #     try:
        #         data = json.loads(s)   # JSON -> dict
        #         print(f"DEBUG: JSON decode successful\n")
        #         print(f"DEBUG: JSON data: {data}")
        #     except json.JSONDecodeError as e:
        #         print(f"DEBUG: JSONDecodeError at pos={e.pos}, lineno={e.lineno}, colno={e.colno}: {e.msg}")
        #         start = max(0, e.pos - 60)
        #         end = min(len(s), e.pos + 60)
        #         print("DEBUG: Context around error:")
        #         print(s[start:end])
        #         raise
        # else:
        #     print(f"DEBUG:⚠Unknown response type: {type(agent_response)}")
        #     data = None

        # # 2) 从 dict 里取 payment_info
        # if isinstance(data, dict):
        #     payment_info = data.get("payment_data", {}).get("payment_info")
        #     print(f"DEBUG: Payment info: {payment_info}")
      
        # Check if we successfully extracted payment info
        if payment_info:
            print("DEBUG: 402 Flag Detected. Triggering Payment Handler.")
            return await self._handle_payment_required(payment_info)
        return agent_response
    
    async def _handle_payment_required(
        self, payment_info: str,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Handle 402 Payment Required response by delegating to accountant agent.
        
        Args:
            payment_data: Payment data from the 402 response
            user_profile: User profile for payment decision
            url: Original URL that requires payment
        
        Returns:
            Content retrieved by accountant agent, or rejection message
        """
        print("\n" + "="*50)
        print("402 PAYMENT REQUIRED DETECTED")
        print("="*50)        
        # Default user profile if not provided
        if not user_profile:
            user_profile = {
                "user_id": "default_guest",
                "tier": "standard",
                "custom_budget_limit": 0.1,  # Default 0.1 SOL
                "preference": "user has a neutral preference for news content"
            }
        # Delegate entire payment and content retrieval to accountant agent
        print("\nDelegating payment evaluation and content retrieval to Accountant Agent...")
        result = await run_accountant_service(payment_info, user_profile)
        
        return result
    
    async def cleanup(self):
        """Cleanup MCP client connection"""
        if self.mcp_client:
            # MultiServerMCPClient may not have a disconnect method
            # Try to clean up gracefully if the method exists
            try:
                await self.mcp_client.disconnect()
            except AttributeError:
                # disconnect() method doesn't exist - this is fine, cleanup happens automatically
                pass
            except Exception:
                # Ignore any other cleanup errors
                pass


async def retriv_run_agent(
    context: str, 
    user_profile: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to run the news retrieval agent.
    
    Args:
        context: Search context for news retrieval
        user_profile: Optional user profile for payment decisions if 402 is encountered
    """
    agent = NewsRetrievalAgent(context)
    try:
        result = await agent.run(user_profile=user_profile)
        return result
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    # Example usage
    context = "Search for news about Apple Inc. (AAPL) and recent technology developments"
    result = asyncio.run(retriv_run_agent(context))
    print("\n" + "="*50)
    print("AGENT RESPONSE:")
    print("="*50)
    print(result)