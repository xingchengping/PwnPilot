# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import json
import re
import paramiko
import uuid
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
from openai import AsyncOpenAI

# ==========================================
# 1. 核心配置区
# ==========================================
CONFIG = {
    "LANGUAGE": "",      # "en" 或 "zh"
    "API_KEY": "",
    "BASE_URL": "",
    "MODEL_NAME": "",
    "KALI_HOST": "",
    "KALI_PORT": "",
    "KALI_USER": "",
    "KALI_PASS": "",
    "SESSIONS_DIR": ""
}

CONFIG_FILE = "PwnPilot_config.json"

def init_config():
    global CONFIG
    if CONFIG.get("API_KEY", "").strip() != "":
        if not CONFIG.get("LANGUAGE"):
            CONFIG["LANGUAGE"] = "zh"
        if not CONFIG.get("KALI_PORT"):
            CONFIG["KALI_PORT"] = 22
        if not CONFIG.get("SESSIONS_DIR"):
            CONFIG["SESSIONS_DIR"] = "sessions"
        CONFIG["KALI_PORT"] = int(CONFIG["KALI_PORT"])
        return

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
                CONFIG.update(saved_config)
                return
        except Exception as e:
            print(f"[!] Error reading {CONFIG_FILE}: {e}")

    print("==================================================")
    print("  PwnPilot V2.0 Initial Setup Wizard")
    print("==================================================")
    while True:
        lang_choice = input("Select Language (1. English, 2. 中文) [default: 1]: ").strip()
        if lang_choice in ["1", "2", ""]:
            lang = "zh" if lang_choice == "2" else "en"
            break

    CONFIG["LANGUAGE"] = lang

    if lang == "en":
        print("\n[!] Configuration missing. Please enter the following details:")
        CONFIG["API_KEY"] = input("1. LLM API Key: ").strip()
        CONFIG["BASE_URL"] = input("2. API Base URL (e.g., https://api.deepseek.com/v1): ").strip()
        CONFIG["MODEL_NAME"] = input("3. Model Name (e.g., deepseek-reasoner): ").strip()
        CONFIG["KALI_HOST"] = input("4. Kali IP Address (e.g., 192.168.0.100): ").strip()
        port_input = input("5. Kali SSH Port [default 22]: ").strip()
        CONFIG["KALI_PORT"] = int(port_input) if port_input else 22
        CONFIG["KALI_USER"] = input("6. Kali Username (e.g., root): ").strip()
        CONFIG["KALI_PASS"] = input("7. Kali Password: ").strip()
        s_dir = input("8. Sessions Storage Directory [default 'sessions']: ").strip()
        CONFIG["SESSIONS_DIR"] = s_dir if s_dir else "sessions"
        print(f"\n[+] Setup complete! Saving to {CONFIG_FILE}...")
    else:
        print("\n[!] 检测到配置为空，请输入以下配置信息：")
        CONFIG["API_KEY"] = input("1. 大模型 API_KEY: ").strip()
        CONFIG["BASE_URL"] = input("2. API Base URL (例如 https://api.deepseek.com/v1): ").strip()
        CONFIG["MODEL_NAME"] = input("3. 模型名称 (例如 deepseek-reasoner): ").strip()
        CONFIG["KALI_HOST"] = input("4. Kali IP地址 (例如 192.168.0.100): ").strip()
        port_input = input("5. Kali SSH端口 [默认 22]: ").strip()
        CONFIG["KALI_PORT"] = int(port_input) if port_input else 22
        CONFIG["KALI_USER"] = input("6. Kali 用户名 (例如 root): ").strip()
        CONFIG["KALI_PASS"] = input("7. Kali 密码: ").strip()
        s_dir = input("8. 会话历史存储目录 [默认 'sessions']: ").strip()
        CONFIG["SESSIONS_DIR"] = s_dir if s_dir else "sessions"
        print(f"\n[+] 配置完成！正在保存至 {CONFIG_FILE}...")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=4)

init_config()

SESSIONS_DIR = CONFIG["SESSIONS_DIR"]
os.makedirs(SESSIONS_DIR, exist_ok=True)

# ==========================================
# 2. 国际化 (i18n) 语言字典及系统提示词核心
# ==========================================
LANG_MAP = {
    "en": {
        "title": "PwnPilot V2.0",
        "sessions_label": "OPERATIONS",
        "no_task": "Awaiting Directives",
        "input_placeholder": "Input strategy or command AI...",
        "pty_status": "(PTY: Human-AI Shared)",
        "modal_title": "Initialize Operation",
        "cancel": "Abort",
        "confirm": "Initialize",
        "new_task": "New Operation",
        "new_task_placeholder": "Codename / Target",
        "create": "Create",
        "ws_connected": "Agent Neural Link Established.",
        "sys_ready": "System Online. Select or create an operation.",
        "ai_thinking": "Processing OODA Loop...",
        "pty_active": "LINK ACTIVE",
        "pty_offline": "LINK OFFLINE",
        "pty_success": "[+] Neural PTY Bridge Active. Operator and Agent synchronised.",
        "msg_stop_alert": "[!] HALT signal received. Agent standing by.",
        "backend_ssh_fail": "[SSH Link Failure]",
        "backend_ai_thinking": "[*] Agent executing cognitive framework...",
        "backend_ai_error": "[-] Neural parsing failure:",
        "backend_task_done": "[🚀] Agent reports objective complete.",
        "backend_action_end": "[*] Agent awaiting Operator guidance...",
        "human_cmd_prefix": "[Operator Input]: ",
        "screen_echo_prefix": "[Terminal Echo Window]:",
        "screen_echo_suffix": "↑ Acknowledge the state above. Execute your OODA loop.",
        "ai_action_label": "Agent Executing",
        "system_prompt": """You are an elite, autonomous Red Team Agent powered by advanced tactical logic, operating in a persistent, shared PTY.

[CORE OPERATIONAL FRAMEWORK: The OODA Loop]
Your decisions must be based on objective facts and rigorous deduction. Blind guessing is strictly prohibited.
1. Observe: Analyze the terminal output. Errors (e.g., 403, 500) are critical intelligence.
2. Orient: Integrate current findings to build a global tactical view.
3. Decide: Formulate the next phase of recon or exploitation. 
4. Act: Issue precise terminal commands.

[TACTICAL DIRECTIVES]
- [Reconnaissance First]: Gather facts before attempting any exploit.
- [State Awareness]: You are in an interactive session. Commands must fit the current active tool's prompt (e.g., msfconsole).
- [Output Management]: Use pipes/regex for massive output, but read whole files if logic dictates.

[COMMUNICATION PROTOCOL]
1. Free Thought: Use natural language and `<think>` tags freely for OODA reasoning.
2. Action Execution: Commands MUST be strictly wrapped in `<cmd>` and `</cmd>`. Example: `<cmd>curl -s http://target/api</cmd>`
3. [CONTINUOUS EXECUTION - CRITICAL]: Never just state your plan without acting! If the objective is not met, your response MUST include a `<cmd>` tag to execute the next step. Do NOT ask for permission to proceed.
4. Mission Termination: Output `<done></done>` ONLY when the overall objective is fully accomplished or you absolutely require human intervention (e.g., solving a captcha).
"""
    },
    "zh": {
        "title": "PwnPilot V2.0",
        "sessions_label": "战术行动组",
        "no_task": "等待战略指示",
        "input_placeholder": "与 AI 协同分析 或 下达指令",
        "pty_status": "(终端链路: 人机协同)",
        "modal_title": "新建渗透任务",
        "cancel": "取消",
        "confirm": "建立",
        "new_task": "开启新目标",
        "new_task_placeholder": "输入行动代号/目标名称",
        "create": "创建",
        "ws_connected": "Agent 神经链路已接入。",
        "sys_ready": "控制台就绪。请从左侧选择或开启一项新的战术行动。",
        "ai_thinking": "OODA 循环推演中...",
        "pty_active": "LINK ACTIVE",
        "pty_offline": "LINK OFFLINE",
        "pty_success": "[+] 神经 PTY 桥接成功。人类督导与 AI 已实现同屏同步。",
        "msg_stop_alert": "[!] 接收到紧急刹车指令，Agent 已挂起。",
        "backend_ssh_fail": "[SSH 链路建立失败]",
        "backend_ai_thinking": "[*] Agent 正在执行认知框架推演...",
        "backend_ai_error": "[-] 大脑神经网络响应异常:",
        "backend_task_done": "[🚀] Agent 判定阶段性战术目标已达成。",
        "backend_action_end": "[*] 当前推演无动作输出，Agent 等待人类督导指示...",
        "human_cmd_prefix": "【督导指示】: ",
        "screen_echo_prefix": "【终端回显视界】(已捕获最大上下文):",
        "screen_echo_suffix": "↑ 查收上述终端环境回显。请严格执行 OODA 战术循环，决定下一步动作。",
        "ai_action_label": "Agent 终端交互",
        "system_prompt": """你是一个由高维度战术逻辑驱动的顶级红队（Red Team）渗透智能体。你当前驻留在一个与人类专家共享的持久化 PTY（伪终端）中。

【核心运行法则: OODA 循环】
你的所有决策必须基于客观事实与严密的逻辑推导，绝不允许盲目试错或基于幻觉的猜测。
1. 观察 (Observe)：仔细审视终端回显。任何错误代码都是关键情报，而非阻碍。
2. 研判 (Orient)：结合当前收集到的网络拓扑、源码逻辑、端口状态，构建全局战术视图。
3. 决策 (Decide)：制定下一步探测或攻击计划，优先选择低噪音、高信息回报的手段。
4. 行动 (Act)：下发精准的终端指令。

【战术纪律 (Tactical Rules)】
- [情报优先]：在尝试任何突破性操作前，必须先掌握目标的环境信息。严禁在没有事实依据的情况下直接发起字典爆破或投递 Payload。
- [状态感知]：时刻牢记你处于一个交互式会话中。如果你启动了 `msfconsole`, `mysql`, `python` 等程序，接下来的命令必须符合该程序的内部交互语法。
- [回显控制]：面对长篇输出，懂得利用工具（如 grep, jq）进行信息提纯，但不畏惧阅读长源码。

【指令交互协议 (Communication Protocol)】
1. 自由推演：你可以用自然语言或 `<think>` 标签尽情展示你的 OODA 推演过程。
2. 动作下发：当你决定在终端执行具体的 shell 命令时，必须且只能将其包裹在 `<cmd>` 和 `</cmd>` 标签内。例如：`<cmd>curl -s http://target/api/user</cmd>`
3. 【绝对禁止只说不做 (Continuous Execution)】：严禁只汇报计划而不执行！只要目标未达成，你的每次回复**必须**包含一个 `<cmd>` 执行块去推进任务！不要询问人类“是否继续”、“我将要执行XX”，请直接执行！
4. 任务挂起：只有当你真正需要人类输入（如验证码）、或者整体目标已彻底完成时，才能输出 `<done></done>`。只要没有 `<done>` 或 `<cmd>`，系统都会认为你发生了故障。
"""
    }
}

T = LANG_MAP[CONFIG["LANGUAGE"]]
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# ==========================================
# 3. 人机共享 PTY 管理器
# ==========================================
class GlobalPTYManager:
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.channel = None
        self.websockets = set()
        self.agent_buffer = []
        self.is_recording = False
        self.lock = asyncio.Lock()
        self.connected = False

    async def connect(self):
        if self.connected:
            return True
        try:
            await asyncio.to_thread(
                self.ssh.connect,
                CONFIG["KALI_HOST"],
                port=CONFIG["KALI_PORT"],
                username=CONFIG["KALI_USER"],
                password=CONFIG["KALI_PASS"],
                timeout=10
            )
            self.channel = self.ssh.invoke_shell(term='xterm-256color', width=150, height=40)
            self.channel.setblocking(0)
            self.connected = True
            asyncio.create_task(self._read_loop())
            return True
        except Exception as e:
            print(f"SSH Error: {e}")
            return False

    async def _read_loop(self):
        while self.connected:
            if self.channel and self.channel.recv_ready():
                data_bytes = self.channel.recv(4096)
                data_str = data_bytes.decode('utf-8', errors='replace')
                if self.is_recording:
                    self.agent_buffer.append(data_str)
                dead_ws = set()
                for ws in self.websockets:
                    try:
                        await ws.send_text(data_str)
                    except:
                        dead_ws.add(ws)
                self.websockets.difference_update(dead_ws)
            else:
                await asyncio.sleep(0.01)

    async def execute_agent_command(self, cmd: str, max_wait: int = 60):
        async with self.lock:
            self.agent_buffer.clear()
            self.is_recording = True
            if cmd:
                marker = f"\r\n\x1b[38;5;208m[🤖 {T['ai_action_label']}]> \x1b[0m{cmd}\r\n"
                for ws in self.websockets:
                    try:
                        await ws.send_text(marker)
                    except:
                        pass
                self.channel.send(cmd + '\n')

            last_len = -1
            settle_count = 0
            elapsed = 0
            # 增加等待时间判定，确保大文件 cat 完整
            while elapsed < max_wait:
                await asyncio.sleep(0.5)
                elapsed += 0.5
                current_len = sum(len(x) for x in self.agent_buffer)
                if current_len == last_len and current_len > 0:
                    settle_count += 1
                    if settle_count >= 4: # 连续2秒无新数据到达视为结束
                        break
                else:
                    settle_count = 0
                    last_len = current_len

            self.is_recording = False
            raw_output = "".join(self.agent_buffer)
            clean_output = ANSI_ESCAPE.sub('', raw_output)
            return clean_output

    def human_input(self, data: str):
        if self.channel:
            self.channel.send(data)

global_pty = GlobalPTYManager()

# ==========================================
# 4. 国际化前端模板（深空黑客战术面板风 V2.0）
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="{{lang_code}}" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
    
    <style>
        @import url('https://gs.jurieo.com/gemini/fonts-googleapis/css2?family=JetBrains+Mono:ital,wght@0,400;0,700;1,400&family=Inter:wght@400;500;600;700&display=swap');
        
        :root { --bg-main: #050505; --bg-sidebar: #0a0a0a; --accent: #0ea5e9; --accent-glow: rgba(14, 165, 233, 0.4); }
        body { background-color: var(--bg-main); color: #d4d4d8; font-family: 'Inter', sans-serif; margin: 0; height: 100vh; display: flex; overflow: hidden; }
        
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: #3f3f46; }

        #sidebar { width: 280px; background: var(--bg-sidebar); border-right: 1px solid #18181b; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); display: flex; flex-direction: column; z-index: 50; box-shadow: 4px 0 30px rgba(0,0,0,0.8);}
        #sidebar.collapsed { transform: translateX(-100%); position: absolute; height: 100%; }
        
        .sidebar-header { padding: 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #18181b; background: #050505;}
        .plus-btn { color: #71717a; cursor: pointer; transition: all 0.2s; background: #18181b; padding: 6px; border-radius: 6px; border: 1px solid #27272a;}
        .plus-btn:hover { color: var(--accent); border-color: var(--accent); background: rgba(14, 165, 233, 0.1); box-shadow: 0 0 10px var(--accent-glow);}
        
        .session-item { padding: 12px 16px; margin: 6px 12px; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #a1a1aa; transition: all 0.2s; border: 1px solid transparent; }
        .session-item:hover { background: #18181b; color: #f4f4f5; }
        .session-item.active { background: rgba(14, 165, 233, 0.1); color: var(--accent); border-color: rgba(14, 165, 233, 0.2); font-weight: 500;}
        .action-btns { display: flex; gap: 4px; opacity: 0; transition: opacity 0.2s; }
        .session-item:hover .action-btns { opacity: 1; }
        .rename-btn, .delete-btn { background: transparent; border: none; cursor: pointer; padding: 4px; border-radius: 4px; font-size: 0.9rem; transition: background 0.2s; display: flex; align-items: center; justify-content: center;}
        .rename-btn:hover { background: rgba(250, 204, 21, 0.2); color: #facc15; }
        .delete-btn:hover { background: rgba(248, 113, 113, 0.2); color: #f87171;}
        
        #chat-section { width: 45%; min-width: 450px; display: flex; flex-direction: column; background: var(--bg-main); border-right: 1px solid #18181b; position: relative;}
        /* 赛博网格背景 */
        .chat-bg { background-image: linear-gradient(#18181b 1px, transparent 1px), linear-gradient(90deg, #18181b 1px, transparent 1px); background-size: 30px 30px; background-position: center center; }
        .chat-container { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 20px; }
        
        .bubble { max-width: 92%; padding: 16px 20px; font-size: 0.9rem; line-height: 1.6; word-wrap: break-word; }
        .bubble-user { align-self: flex-end; background: #18181b; color: #f4f4f5; border: 1px solid #27272a; border-radius: 12px 12px 2px 12px; }
        /* Agent 对话框优化 */
        .bubble-agent { align-self: flex-start; background: rgba(14, 165, 233, 0.05); color: #e0f2fe; border: 1px solid rgba(14, 165, 233, 0.2); border-radius: 12px 12px 12px 2px; backdrop-filter: blur(8px);}
        
        /* 战术推演区块 (兼容 DeepSeek R1) */
        .agent-thought-block { 
            color: #a1a1aa; font-size: 0.85rem; 
            border-left: 2px solid #0ea5e9; 
            padding: 10px 14px; margin-bottom: 16px; 
            background: linear-gradient(90deg, rgba(14, 165, 233, 0.08) 0%, transparent 100%); 
            border-radius: 0 8px 8px 0;
            font-family: 'Inter', sans-serif;
        }
        .thought-header { display: flex; align-items: center; gap: 6px; font-weight: 600; color: #0ea5e9; margin-bottom: 6px; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;}
        
        /* 终端动作区块 */
        .agent-cmd-block { 
            margin: 16px 0 8px 0; font-family: "JetBrains Mono", monospace; font-size: 0.85rem; 
            background: #000000; padding: 12px 16px; border-radius: 6px; 
            border: 1px solid #27272a; border-left: 3px solid #f59e0b; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .cmd-header { color: #f59e0b; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 4px; display: block; font-family: 'Inter', sans-serif; font-weight: 700; letter-spacing: 0.05em;}
        .cmd-content { color: #d4d4d8; }
        
        .system-notice { align-self: center; font-size: 0.75rem; color: #71717a; margin: 12px 0; background: #0a0a0a; padding: 6px 16px; border-radius: 20px; border: 1px solid #18181b; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;}
        
        #terminal-section { flex: 1; background: #000000; display: flex; flex-direction: column; position: relative; z-index: 10;}
        #terminal-container { flex: 1; padding: 12px 16px; overflow: hidden; background: #000000; }
        .xterm .xterm-viewport { overflow-y: auto !important; }
        
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.9); backdrop-filter: blur(4px); z-index: 100; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.2s;}
        .modal.active { display: flex; opacity: 1;}
        .modal-content { background: #0a0a0a; border: 1px solid #27272a; padding: 32px; border-radius: 12px; width: 380px; box-shadow: 0 25px 50px -12px rgba(0,0,0,1); transform: scale(0.95); transition: transform 0.2s;}
        .modal.active .modal-content { transform: scale(1); }
        .input-glow:focus-within { box-shadow: 0 0 0 1px var(--accent); border-color: var(--accent); }
    </style>
</head>
<body>

    <div id="sidebar">
        <div class="sidebar-header">
            <span class="text-[11px] font-bold text-zinc-500 uppercase tracking-[0.15em] flex items-center gap-2">
                <svg class="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                {{sessions_label}}
            </span>
            <div class="plus-btn" onclick="showModal('{{new_task}}', '{{new_task_placeholder}}', '{{create}}')" title="New Operation">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            </div>
        </div>
        <div id="sessionList" class="flex-1 overflow-y-auto py-2"></div>
        <div class="p-4 text-[10px] text-zinc-700 text-center font-mono border-t border-zinc-900">PWNPILOT ENGINE V2.0</div>
    </div>

    <div id="chat-section">
        <div class="h-16 border-b border-[#18181b] flex items-center px-6 justify-between bg-[#050505]/95 backdrop-blur-md shrink-0 shadow-sm z-20">
            <div class="flex items-center gap-4">
                <button onclick="toggleSidebar()" class="text-zinc-600 hover:text-sky-400 transition-colors p-1.5 rounded-md hover:bg-sky-500/10"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg></button>
                <span class="font-semibold text-[13px] text-zinc-300 tracking-wide flex items-center gap-2 uppercase" id="currentSessionTitle">
                    <svg class="w-4 h-4 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                    {{no_task}}
                </span>
            </div>
            <div class="flex items-center gap-2.5">
                <span class="text-[10px] uppercase tracking-wider text-zinc-600 font-bold" id="aiStatusText">OODA CORE</span>
                <span id="aiStatusIndicator" class="w-2 h-2 rounded-full bg-zinc-800 shadow-inner transition-all duration-300"></span>
            </div>
        </div>
        <div id="chatBox" class="chat-container chat-bg">
            <div class="system-notice">{{sys_ready}}</div>
        </div>
        <div class="p-5 bg-[#050505]/95 backdrop-blur-md border-t border-[#18181b] shrink-0">
            <div class="relative flex items-center">
                <input type="text" id="userInput" placeholder="{{input_placeholder}}" class="w-full bg-[#0a0a0a] border border-[#27272a] rounded-lg py-3.5 pl-4 pr-14 text-sm text-zinc-200 focus:outline-none focus:border-sky-500/60 focus:ring-1 focus:ring-sky-500/30 transition-all placeholder-zinc-700 shadow-inner" onkeypress="if(event.key === 'Enter') sendChatMessage()">
                <button onclick="sendChatMessage()" class="absolute right-2.5 p-2 bg-sky-600 hover:bg-sky-500 text-white rounded-md transition-colors shadow-lg flex items-center justify-center">
                    <svg class="w-4 h-4 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M12 5l7 7-7 7"></path></svg>
                </button>
            </div>
        </div>
    </div>

    <div id="terminal-section">
        <div class="h-10 bg-[#0a0a0a] flex items-center px-4 border-b border-[#18181b] shrink-0 justify-between">
            <div class="flex items-center gap-4">
                <div class="text-[11px] text-zinc-500 font-mono tracking-widest ml-1 bg-[#18181b] px-4 py-1.5 rounded-t-md border-t border-l border-r border-[#27272a] mt-2 opacity-90 flex items-center gap-2 shadow-[0_-2px_10px_rgba(0,0,0,0.5)]">
                    <svg class="w-3.5 h-3.5 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                    root@kali:~ {{pty_status}}
                </div>
            </div>
            <div id="termStatus" class="text-[9px] uppercase font-bold tracking-[0.2em] text-red-500/80">{{pty_offline}}</div>
        </div>
        <div id="terminal-container"></div>
    </div>

    <div id="inputModal" class="modal">
        <div class="modal-content">
            <h3 class="font-bold text-lg mb-1 text-zinc-100 uppercase tracking-widest" id="modalTitle">{{modal_title}}</h3>
            <p class="text-xs text-zinc-500 mb-6 font-mono">Initialize a new autonomous operation.</p>
            <div class="input-glow rounded-md border border-zinc-800 bg-[#050505] transition-all mb-8">
                <input type="text" id="modalInput" class="w-full bg-transparent border-none px-4 py-3 text-sm text-zinc-200 focus:outline-none placeholder-zinc-700" autocomplete="off" onkeypress="if(event.key === 'Enter') document.getElementById('modalConfirmBtn').click()">
            </div>
            <div class="flex justify-end gap-3">
                <button onclick="closeModal()" class="px-5 py-2 text-xs font-semibold uppercase tracking-wider text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 rounded-md transition-colors">{{cancel}}</button>
                <button id="modalConfirmBtn" class="px-6 py-2 text-xs font-bold uppercase tracking-wider bg-sky-600 hover:bg-sky-500 text-white rounded-md transition-all shadow-[0_0_15px_rgba(14,165,233,0.2)] hover:shadow-[0_0_20px_rgba(14,165,233,0.4)]">{{confirm}}</button>
            </div>
        </div>
    </div>

    <script>
        let currentSessionId = null; let chatWs = null; let termWs = null;
        let xterm = null; let fitAddon = null;
        let sessionsData = []; 
        const chatBox = document.getElementById('chatBox');
        
        function escapeHtml(str) {
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            }).replace(/[\\uD800-\\uDBFF][\\uDC00-\\uDFFF]/g, function(c) { return c; });
        }
        
        function initTerminal() {
            xterm = new Terminal({
                cursorBlink: true, 
                theme: { background: '#000000', foreground: '#0ea5e9', cursor: '#0ea5e9', selectionBackground: 'rgba(14, 165, 233, 0.3)' },
                fontFamily: '"JetBrains Mono", "Fira Code", monospace', fontSize: 13, disableStdin: false,
                lineHeight: 1.3
            });
            fitAddon = new FitAddon.FitAddon();
            xterm.loadAddon(fitAddon);
            xterm.open(document.getElementById('terminal-container'));
            fitAddon.fit();
            window.addEventListener('resize', () => fitAddon.fit());
            
            xterm.onData(data => { if (termWs && termWs.readyState === WebSocket.OPEN) termWs.send(data); });
        }

        function connectTermWS() {
            termWs = new WebSocket(`ws://${window.location.host}/ws/terminal`);
            termWs.onopen = () => {
                document.getElementById('termStatus').innerText = '{{pty_active}}';
                document.getElementById('termStatus').className = 'text-[9px] uppercase font-bold tracking-[0.2em] text-sky-400';
                xterm.writeln('\\r\\n\\x1b[38;5;39m{{pty_success}}\\x1b[0m\\r\\n');
            };
            termWs.onmessage = (e) => xterm.write(e.data);
            termWs.onclose = () => { 
                document.getElementById('termStatus').innerText = '{{pty_offline}}'; 
                document.getElementById('termStatus').className = 'text-[9px] uppercase font-bold tracking-[0.2em] text-red-500/80'; 
            };
        }

        function connectChatWS(sessionId) {
            if (chatWs) chatWs.close();
            chatWs = new WebSocket(`ws://${window.location.host}/ws/chat/${sessionId}`);
            chatWs.onopen = () => { 
                document.getElementById('aiStatusIndicator').className = 'w-2 h-2 rounded-full bg-sky-500 shadow-[0_0_8px_rgba(14,165,233,0.8)]'; 
                document.getElementById('aiStatusText').className = 'text-[10px] uppercase tracking-wider text-sky-400 font-bold';
                appendSystemNotice('{{ws_connected}}');
            };
            chatWs.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === "system") {
                    appendSystemNotice(data.content);
                    if(data.content.includes("{{ai_thinking}}")) {
                        document.getElementById('aiStatusIndicator').className = 'w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)] animate-pulse';
                        document.getElementById('aiStatusText').className = 'text-[10px] uppercase tracking-wider text-amber-400 font-bold';
                    } else {
                        document.getElementById('aiStatusIndicator').className = 'w-2 h-2 rounded-full bg-sky-500 shadow-[0_0_8px_rgba(14,165,233,0.8)]';
                        document.getElementById('aiStatusText').className = 'text-[10px] uppercase tracking-wider text-sky-400 font-bold';
                    }
                } else if (data.type === "agent") appendAgentMessage(data);
                else if (data.type === "history") {
                    chatBox.innerHTML = '';
                    data.messages.forEach(msg => {
                        if (msg.role === 'user' && !msg.content.includes("{{screen_echo_prefix}}")) appendUserMessage(msg.content.replace('{{human_cmd_prefix}}', ''));
                        else if (msg.role === 'assistant') appendAgentMessage({text: msg.content});
                    });
                }
            };
        }

        function appendUserMessage(text) { chatBox.innerHTML += `<div class="bubble bubble-user">${escapeHtml(text)}</div>`; chatBox.scrollTop = chatBox.scrollHeight; }
        function appendSystemNotice(text) { chatBox.innerHTML += `<div class="system-notice">${escapeHtml(text)}</div>`; chatBox.scrollTop = chatBox.scrollHeight; }
        
        function appendAgentMessage(data) {
            let html = `<div class="bubble bubble-agent">`;
            let formattedText = escapeHtml(data.text);
            
            // 原生解析 R1 OODA 推演过程标签
            formattedText = formattedText.replace(/&lt;think&gt;([\\s\\S]*?)&lt;\\/think&gt;/g, 
                '<div class="agent-thought-block"><div class="thought-header"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg> OODA Loop Deduction</div>$1</div>');
            
            // 解析 <cmd> 终端命令标签
            formattedText = formattedText.replace(/&lt;cmd&gt;([\\s\\S]*?)&lt;\\/cmd&gt;/g, 
                '<div class="agent-cmd-block"><span class="cmd-header">Execute Action</span><span class="cmd-content">$1</span></div>');
            
            // 解析 <done> 标签
            formattedText = formattedText.replace(/&lt;done.*?&gt;/g, 
                '<span class="inline-block mt-4 text-[10px] font-mono uppercase bg-emerald-900/40 text-emerald-400 px-3 py-1.5 rounded-sm border border-emerald-800/50 tracking-wider">✔️ Objective Concluded</span>');

            html += `<div class="font-medium tracking-wide whitespace-pre-wrap leading-relaxed">${formattedText}</div>`;
            html += `</div>`;
            chatBox.innerHTML += html;
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function sendChatMessage() {
            const input = document.getElementById('userInput');
            if (!input.value.trim() || !chatWs) return;
            appendUserMessage(input.value);
            chatWs.send(input.value);
            input.value = '';
        }

        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('collapsed'); setTimeout(() => fitAddon.fit(), 300); }

        async function loadSessions() {
            const res = await fetch('/api/sessions');
            sessionsData = await res.json();
            let html = '';
            for (let s of sessionsData) {
                const safeTitle = escapeHtml(s.title);
                html += `
                    <div class="session-item group ${s.id === currentSessionId ? 'active' : ''}" onclick="switchSession('${s.id}')">
                        <div class="flex items-center gap-2.5 overflow-hidden flex-1">
                            <svg class="w-3.5 h-3.5 shrink-0 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                            <span class="truncate tracking-wide">${safeTitle}</span>
                        </div>
                        <div class="action-btns shrink-0">
                            <button class="rename-btn text-zinc-500" onclick="renameSession('${s.id}', event)" title="Rename">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>
                            </button>
                            <button class="delete-btn text-zinc-500" onclick="deleteSession('${s.id}', event)" title="Delete">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                            </button>
                        </div>
                    </div>`;
            }
            document.getElementById('sessionList').innerHTML = html;
        }
        
        function switchSession(id) { 
            const session = sessionsData.find(s => s.id === id);
            if(session) {
                currentSessionId = id; 
                document.getElementById('currentSessionTitle').innerHTML = `<svg class="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg> ` + escapeHtml(session.title); 
                loadSessions(); 
                connectChatWS(id); 
            }
        }
        
        async function renameSession(id, event) {
            event.stopPropagation();
            const session = sessionsData.find(s => s.id === id);
            if(!session) return;

            let newTitle = prompt('Rename operation codename:', session.title);
            if (newTitle && newTitle.trim() && newTitle.trim() !== session.title) {
                const res = await fetch(`/api/sessions/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle.trim() })
                });
                if (res.ok) {
                    if (currentSessionId === id) {
                        document.getElementById('currentSessionTitle').innerHTML = `<svg class="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg> ` + escapeHtml(newTitle.trim());
                    }
                    loadSessions();
                }
            }
        }
        
        function showModal(title, placeholder, btnText) {
            document.getElementById('modalTitle').innerText = title;
            document.getElementById('modalInput').placeholder = placeholder;
            document.getElementById('modalConfirmBtn').onclick = async () => { 
                const title_val = document.getElementById('modalInput').value.trim();
                if(title_val) {
                    const res = await fetch('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: title_val }) });
                    const data = await res.json();
                    await loadSessions();
                    switchSession(data.id);
                }
                closeModal(); 
            };
            document.getElementById('inputModal').classList.add('active');
            setTimeout(() => document.getElementById('modalInput').focus(), 100);
        }

        function closeModal() { 
            document.getElementById('inputModal').classList.remove('active'); 
            document.getElementById('modalInput').value = ''; 
        }
        
        async function deleteSession(id, e) { 
            e.stopPropagation(); 
            if(confirm('Abort and purge this operation? This action is irreversible.')) {
                await fetch(`/api/sessions/${id}`, { method: 'DELETE' }); 
                if (currentSessionId === id) { 
                    currentSessionId = null; 
                    chatBox.innerHTML = '<div class="system-notice">{{sys_ready}}</div>'; 
                    document.getElementById('currentSessionTitle').innerHTML = `<svg class="w-4 h-4 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg> {{no_task}}`; 
                    if(chatWs) chatWs.close();
                } 
                loadSessions(); 
            }
        }

        window.onload = () => { initTerminal(); connectTermWS(); loadSessions(); }
    </script>
</body>
</html>
"""

HTML_RENDERED = HTML_TEMPLATE.replace("{{lang_code}}", CONFIG["LANGUAGE"])
for key, val in T.items():
    HTML_RENDERED = HTML_RENDERED.replace(f"{{{{{key}}}}}", val)

# ==========================================
# 5. 后端API与WebSocket
# ==========================================
app = FastAPI()

class SessionCreate(BaseModel):
    title: str

@app.post("/api/sessions")
async def create_session(data: SessionCreate):
    sid = str(uuid.uuid4())[:8]
    meta = {"id": sid, "title": data.title, "created_at": datetime.now().isoformat()}
    with open(os.path.join(SESSIONS_DIR, f"{sid}.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")
    return meta

@app.get("/api/sessions")
async def get_sessions():
    sessions = []
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    for file in sorted(os.listdir(SESSIONS_DIR), reverse=True):
        if file.endswith(".jsonl"):
            with open(os.path.join(SESSIONS_DIR, file), "r", encoding="utf-8") as f:
                first_line = f.readline()
                if first_line:
                    try:
                        sessions.append(json.loads(first_line))
                    except:
                        pass
    return sessions

@app.put("/api/sessions/{session_id}")
async def rename_session(session_id: str, data: SessionCreate):
    file_path = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Session not found")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        raise HTTPException(status_code=400, detail="Corrupted session file")
    
    meta = json.loads(lines[0])
    meta["title"] = data.title
    lines[0] = json.dumps(meta) + "\n"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return {"status": "ok", "id": session_id, "title": data.title}

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        os.remove(os.path.join(SESSIONS_DIR, f"{session_id}.jsonl"))
    except Exception:
        pass
    return {"status": "ok"}

@app.websocket("/ws/terminal")
async def terminal_endpoint(websocket: WebSocket):
    await websocket.accept()
    global_pty.websockets.add(websocket)

    if not global_pty.connected:
        success = await global_pty.connect()
        if not success:
            await websocket.send_text(f"\r\n\x1b[31m{T['backend_ssh_fail']}\x1b[0m\r\n")
            return

    try:
        while True:
            data = await websocket.receive_text()
            global_pty.human_input(data)
    except WebSocketDisconnect:
        global_pty.websockets.discard(websocket)

class HITLAgent:
    def __init__(self, websocket: WebSocket, session_id: str):
        self.ws = websocket
        self.file_path = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
        self.client = AsyncOpenAI(api_key=CONFIG["API_KEY"], base_url=CONFIG["BASE_URL"])
        self.memory = [{"role": "system", "content": T["system_prompt"]}]
        self.is_running = False
        self.load_history()

    def load_history(self):
        if not os.path.exists(self.file_path):
            return
        with open(self.file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[1:]:
                try:
                    self.memory.append(json.loads(line))
                except:
                    pass

    def save_message(self, role: str, content: str):
        msg = {"role": role, "content": content}
        self.memory.append(msg)
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg) + "\n")

    async def run_autonomous_loop(self):
        self.is_running = True
        consecutive_errors = 0
        self.consecutive_no_cmd = 0

        if not global_pty.connected:
            await global_pty.connect()

        while self.is_running:
            await self.ws.send_json({"type": "system", "content": T["backend_ai_thinking"]})
            try:
                response = await self.client.chat.completions.create(
                    model=CONFIG["MODEL_NAME"],
                    messages=self.memory,
                    temperature=0.7
                )
                reply_text = response.choices[0].message.content
                self.save_message("assistant", reply_text)
                
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors > 3:
                    self.is_running = False
                    break
                await asyncio.sleep(2)
                continue

            consecutive_errors = 0
            
            # 使用正则提取 <cmd> 标签内的命令
            cmd_match = re.search(r'<cmd>(.*?)</cmd>', reply_text, re.DOTALL | re.IGNORECASE)
            cmd = cmd_match.group(1).strip() if cmd_match else ""
            
            # 检查是否有 <done> 标志
            is_done = bool(re.search(r'<done.*?>', reply_text, re.IGNORECASE))

            await self.ws.send_json({
                "type": "agent",
                "text": reply_text
            })

            # 如果任务结束，停止循环
            if is_done:
                await self.ws.send_json({"type": "system", "content": T["backend_task_done"]})
                self.is_running = False
                break

            # 如果有命令，则执行
            if cmd:
                self.consecutive_no_cmd = 0
                cmd_result = await global_pty.execute_agent_command(cmd)
                
                # 【核心框架优化】：扩充回显捕获极限至 20,000 字符，确保 OODA 循环输入完整
                trunc_result = cmd_result[-20000:]
                self.save_message("user", f"{T['screen_echo_prefix']}\n{trunc_result}\n{T['screen_echo_suffix']}")
                await asyncio.sleep(1.5)
            else:
                # 触发自动督导机制 (Auto-Nudge)
                self.consecutive_no_cmd += 1
                if self.consecutive_no_cmd >= 3:
                    await self.ws.send_json({"type": "system", "content": T["backend_action_end"]})
                    self.is_running = False
                    break
                else:
                    nudge_msg = "【System Auto-Nudge】: You reasoned but provided no <cmd> execution block. Please strictly follow [CONTINUOUS EXECUTION]. Execute your next step via <cmd>, or output <done></done> if waiting for human." if CONFIG["LANGUAGE"] == "en" else "【系统自动督导】: 你进行了推演但未下发任何 <cmd> 指令。请遵循「持续行动」法则，直接使用 <cmd> 执行你的下一步计划！若确实需人类介入请输出 <done></done>。"
                    self.save_message("user", nudge_msg)
                    await self.ws.send_json({"type": "system", "content": "[-] 触发自动督导：鞭策 Agent 继续执行..."})
                    await asyncio.sleep(1)

@app.get("/")
async def get():
    return HTMLResponse(HTML_RENDERED)

@app.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    agent = HITLAgent(websocket, session_id)
    if len(agent.memory) > 1:
        await websocket.send_json({"type": "history", "messages": agent.memory[1:]})

    loop_task = None
    try:
        while True:
            user_msg = await websocket.receive_text()
            agent.save_message("user", f"{T['human_cmd_prefix']}{user_msg}")

            if "停" in user_msg or "stop" in user_msg.lower():
                agent.is_running = False
                if loop_task:
                    loop_task.cancel()
                await websocket.send_json({"type": "system", "content": T["msg_stop_alert"]})
                continue

            if not agent.is_running:
                loop_task = asyncio.create_task(agent.run_autonomous_loop())

    except WebSocketDisconnect:
        agent.is_running = False
        if loop_task:
            loop_task.cancel()

if __name__ == "__main__":
    if CONFIG["LANGUAGE"] == "zh":
        print(f"[*] 存储引擎初始化 -> {os.path.abspath(SESSIONS_DIR)}")
        print("[*] 启动 PwnPilot V2.0 (OODA 战略引擎)...")
        print("[*] 请在浏览器打开: http://127.0.0.1:8000")
    else:
        print(f"[*] Storage Engine initialized -> {os.path.abspath(SESSIONS_DIR)}")
        print("[*] Starting PwnPilot V2.0 (OODA Strategy Engine)...")
        print("[*] Open your browser: http://127.0.0.1:8000")

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")