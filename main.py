"""
Main entry point for NewsieAI System.
This script acts as a central hub to test different agents and their corresponding MCP services.
"""

import asyncio
import subprocess
import sys
import time
import os
import json
import re
from pathlib import Path
from typing import Optional
from wallet import wallet
from datetime import datetime

# 尝试导入 requests (用于 Accountant 测试)
try:
    import requests
except ImportError:
    print("❌ Critical: 'requests' library missing. Install via: pip install requests")
    sys.exit(1)

from dotenv import load_dotenv

# 导入 Agent 入口
# 确保 agents 目录下有 __init__.py 或者 Python path 设置正确
try:
    from agents.retriv import retriv_run_agent
    from agents.accountant import run_accountant_service
    from agents.personal_assistant import run_personal_assistant
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Ensure you are running from the project root (D:\\ICP\\newsieai)")
    sys.exit(1)

load_dotenv()

# =================================================================
# 🛠️ 通用工具函数 (Helper Functions)
# =================================================================

def check_port_open(port: int) -> bool:
    """Check if a local port is open (service running)"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", port))
        sock.close()
        return result == 0
    except:
        return False

def ensure_mcp_server_running(script_name: str, port_env_var: str, default_port: int) -> Optional[subprocess.Popen]:
    """
    Generic function to ensure a specific MCP server is running.
    Returns the process object if started, or None if already running or failed.
    """
    target_port = int(os.getenv(port_env_var, default_port))
    
    # 1. 检查是否已经在运行
    if check_port_open(target_port):
        print(f"✅ Service '{script_name}' already detected on port {target_port}")
        return None

    # 2. 定位脚本路径
    # 假设 tools 在根目录下的 tools/ 文件夹
    project_root = Path(__file__).parent
    script_path = project_root / "tools" / script_name
    
    if not script_path.exists():
        print(f"❌ MCP script not found: {script_path}")
        return None

    print(f"Starting MCP Service: {script_name} (Port: {target_port})...")
    
    # 3. 启动子进程
    # 关键：设置 cwd 为项目根目录，确保 imports 正常
    try:
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            stdout=subprocess.PIPE, # 捕获输出防止刷屏，或者设为 None 显示在控制台
            stderr=None             # 让错误直接显示，方便调试
        )
        
        # 等待启动
        print("Waiting 3s for startup...")
        time.sleep(3)
        
        if check_port_open(target_port):
            print(f"Successfully started {script_name}")
            return process
        else:
            print(f"Service started but port {target_port} is not responding yet.")
            return process
            
    except Exception as e:
        print(f"❌ Failed to start subprocess: {e}")
        return None

# =================================================================
# Test Wrappers
# =================================================================

async def test_news_agent():
    """
    Wrapper for News Retrieval Agent Test
    Dependencies: retrival_tools.py (Search MCP)
    """
    print("\n" + "="*50)
    print("TESTING: NEWS RETRIEVAL AGENT")
    print("="*50)

    # 1. 确保 Search MCP 启动
    mcp_process = ensure_mcp_server_running("retrival_tools.py", "SEARCH_HTTP_PORT", 8001)
    mcp_process2 = ensure_mcp_server_running("tool_pay.py", "PAY_HTTP_PORT", 8007)


    try:
        print("Enter context for news search (or press Enter for default):")
        print("   Ex: 'Latest news about Tesla (TSLA)'")
        context = input("   > ").strip()
        
        if not context:
            context = "Search for news about Apple Inc. (AAPL) and recent technology developments"
            print(f"   Using default: {context}")

        print(f"Agent is running... (Context: {context})")
    
        result = await retriv_run_agent(context)
        
        print("\n" + "-"*50)
        print("AGENT RESPONSE:")
        print("-"*50)
        print(result)

    finally:
        # 清理 Search MCP (如果是由本函数启动的)
        if mcp_process:
            print("\n🛑 Stopping Search MCP...")
            mcp_process.terminate()
            mcp_process2.terminate()

async def test_accountant_agent():
    """
    Wrapper for Accountant Agent Test
    Dependencies: tool_pay.py (Pay MCP) + test_server.py (External)
    """
    print("\n" + "="*50)
    print("TESTING: ACCOUNTANT AGENT (Full Cycle)")
    print("="*50)

    # 1. 确保 Pay MCP 启动
    mcp_process = ensure_mcp_server_running("tool_pay.py", "PAY_HTTP_PORT", 8007)

    # 2. 定义测试用户画像
    vip_profile = {
        "user_id": "main_tester_01",
        "tier": "VIP_PLATINUM",
        "custom_budget_limit": 0.1,
        "preference": "the user is very interested in crypto market"
    }

    try:
        server_url = "http://localhost:8000/premium-content"
        print(f"Connecting to Content Server: {server_url}")
        
        try:
            resp = requests.get(server_url)
        except requests.exceptions.ConnectionError:
            print("❌ Connection Failed: Could not reach test_server.py.")
            print(" TIP: Open a new terminal and run: python test_server.py")
            return

        if resp.status_code == 402:
            print("✅ 402 Payment Required triggered.")
            bill_data = resp.json()
            print(bill_data)
            # 提取 payload
            payload = bill_data

            
            print(f"\n  Invoking Accountant Agent (Budget: {vip_profile['custom_budget_limit']} SOL)...")
            
            # 调用 Agent
            agent_res = await run_accountant_service(payload, user_profile=vip_profile)
            print(f" Agent Decision:\n{agent_res}")
            
            # 验证结果
            if "PAYMENT_SUCCESSFUL" in agent_res:
                match = re.search(r"PAYMENT_SUCCESSFUL:\s*([A-Za-z0-9]+)", agent_res)
                if match:
                    tx_hash = match.group(1).strip()
                    print(f"\n  Payment Hash Found: {tx_hash}")
                    print(" Waiting 10s for chain confirmation...")
                    await asyncio.sleep(10)
                    
                    print("  Redeeming Content...")
                    final_resp = requests.get(server_url, headers={"Authorization": f"Bearer {tx_hash}"})
                    
                    if final_resp.status_code == 200:
                        print("\n SUCCESS! Content Retrieved:")
                        print(json.dumps(final_resp.json(), indent=2, ensure_ascii=False))
                    else:
                        print(f"❌ Verification Failed: {final_resp.text}")
            else:
                print("\n  Agent did not execute payment.")
        
        elif resp.status_code == 200:
            print("  Server returned 200 OK (Is it already paid/free?)")
        else:
            print(f"❌ Unexpected status code: {resp.status_code}")

    finally:
        # 清理 Pay MCP (如果是由本函数启动的)
        if mcp_process:
            print("\n🛑 Stopping Pay MCP...")
            mcp_process.terminate()


async def test_personal_assistant_agent():
    """
    Wrapper to test the Personal Assistant Agent.
    Dependencies: retrival_tools.py (Search MCP) for news gathering.
    """
    print("\n" + "="*50)
    print("TESTING: PERSONAL ASSISTANT AGENT")
    print("="*50)

    # Ensure Search MCP is running for retriv agent
    mcp_process = ensure_mcp_server_running("retrival_tools.py", "SEARCH_HTTP_PORT", 8001)
    mcp_process2 = ensure_mcp_server_running("tool_pay.py", "PAY_HTTP_PORT", 8007)

    try:
        # ---- Collect user profile ----
        print("\n[User Profile]")
        user_id = input("User ID (default: demo_user): ").strip() or "demo_user"
        timezone = input("Timezone (default: UTC): ").strip() or "UTC"

        pref_times_raw = input("Preferred notification times (HH:MM, comma separated, e.g. 09:00,21:30) [optional]: ").strip()
        if pref_times_raw:
            preferred_notification_times = [t.strip() for t in pref_times_raw.split(",") if t.strip()]
        else:
            preferred_notification_times = []

        content_prefs_raw = input("Content preferences (e.g. tech,crypto,macro; comma separated) [optional]: ").strip()
        if content_prefs_raw:
            content_preferences = [c.strip() for c in content_prefs_raw.split(",") if c.strip()]
        else:
            content_preferences = []

        user_profile = {
            "user_id": user_id,
            "timezone": timezone,
            "preferred_notification_times": preferred_notification_times,
            "content_preferences": content_preferences,
        }

        # ---- Collect a very simple schedule log ----
        print("\n[Schedule Log]")
        add_schedule = input("Add a simple busy block for today? (y/N): ").strip().lower()
        schedule_log = []
        if add_schedule == "y":
            start_time = input("Start time (YYYY-MM-DD HH:MM, default: today 09:00): ").strip()
            end_time = input("End time   (YYYY-MM-DD HH:MM, default: today 11:00): ").strip()
            title = input("Title (default: Busy Block): ").strip() or "Busy Block"



            today = datetime.now().strftime("%Y-%m-%d")

            if not start_time:
                start_time = f"{today} 09:00"
            if not end_time:
                end_time = f"{today} 11:00"

            schedule_log.append(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "title": title,
                }
            )

        # ---- Input time & content ----
        print("\n[Gathering Request]")
        input_time = input("Input time when you invoke this assistant (HH:MM or full 'YYYY-MM-DD HH:MM', default: now): ").strip() or None
        input_content = input("What do you want to explore? (default: today's key market and tech news): ").strip()
        if not input_content:
            input_content = "today's key market and tech news"

        user_ip = input("User IP for mock location lookup (optional, e.g. 203.0.113.10): ").strip() or None

        print("\n🚀 Running Personal Assistant Agent...")
        res = await run_personal_assistant(
            user_profile=user_profile,
            schedule_log=schedule_log,
            input_time=input_time,
            input_content=input_content,
            user_ip=user_ip,
        )

        print("\n" + "-"*50)
        print("PERSONAL ASSISTANT PLANNING SUMMARY:")
        print("-"*50)
        # Pretty-print but truncate full gathered info for readability
        summary = dict(res)
        gathered_full = summary.pop("gathered_info_full", None)
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if gathered_full:
            print(f"GATHERED INFO (FULL) SUCCESSFULLY")
            save_dir = r"D:\ICP\newsieai\datalog"
            
            # 2. 如果文件夹不存在，自动创建
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                print(f"Created directory: {save_dir}")

            # 3. 生成带时间戳的文件名 (例如: news_20250107_103055.txt)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"news_{timestamp}.txt"
            file_path = os.path.join(save_dir, filename)

            # 4. 写入文件 (使用 utf-8 编码防止中文乱码)
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(str(gathered_full))
                print(f"✅ Success! Content saved to: {file_path}")
            except Exception as e:
                print(f"❌ Failed to save file: {e}")

            # ---------------------------------------------------------
            # 原有的打印逻辑 (去掉切片以显示全部)
            # ---------------------------------------------------------
            print("\n" + "-"*50)
            print("GATHERED INFO (FULL):at datalog folder")
            print("-"*50)

    finally:
        if mcp_process:
            print("\n🛑 Stopping Search MCP...")
            mcp_process.terminate()
            mcp_process2.terminate()

# =================================================================
# 🎮 主菜单 (Main Menu)
# =================================================================

def main():
    while True:
        print("\n" + "="*40)
        print("   NewsieAI Agent Control Center")
        print("="*40)
        print("1. Test News Retrieval Agent (Search)")
        print("2. Test Accountant Agent (Payment)")
        print("3. Test Personal Assistant Agent")
        print("4. Exit")
        
        choice = input("\nSelect an option (1-3): ").strip()
        
        if choice == "1":
            try:
                asyncio.run(test_news_agent())
            except KeyboardInterrupt:
                print("\n⚠️ Test Interrupted.")
            except Exception as e:
                print(f"❌ Error: {e}")
                
        elif choice == "2":
            print("\n⚠️  NOTE: Ensure 'python test_server.py' is running in another terminal!")
            input("Press Enter to continue...")
            try:
                asyncio.run(test_accountant_agent())
            except KeyboardInterrupt:
                print("\n⚠️ Test Interrupted.")
            except Exception as e:
                print(f"❌ Error: {e}")

        elif choice == "3":
            try:
                asyncio.run(test_personal_assistant_agent())
            except KeyboardInterrupt:
                print("\n⚠️ Test Interrupted.")
            except Exception as e:
                print(f"❌ Error: {e}")

        elif choice == "4":
            print(" Exiting...")
            break
        else:
            print("❌ Invalid selection.")

if __name__ == "__main__":
    main()