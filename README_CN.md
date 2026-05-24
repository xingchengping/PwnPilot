PwnPilot（本地 SSH 共享终端 + LLM 协作控制台）

这是一个运行在本机的 Web 控制台：浏览器左侧是会话列表与对话区，右侧是通过 SSH 连接到远端主机的共享交互式终端（PTY）。后端通过大模型把“对话指令 + 终端回显”串成一个循环，用于在你明确授权的环境里做自动化操作与人机协作。

功能概览

- 浏览器内嵌终端（xterm.js），实时显示 SSH 交互式 shell 输出
- 人类与自动化代理共享同一个终端（同屏输入/同屏回显）
- 会话管理：新建/删除会话、按会话持久化聊天与回显
- 中英双语界面（由配置项 LANGUAGE 控制）
- 通过兼容 OpenAI 协议的服务端调用大模型（AsyncOpenAI + base_url）

运行环境

- Python 3.10+（建议 3.11）
- 本机浏览器（Chrome / Edge / Firefox 均可）
- 一台可 SSH 登录的主机（你自己的机器或实验环境），可用交互式 shell
- 一个兼容 OpenAI Chat Completions 的 API（支持 base_url 与 model 参数）

安装

建议使用虚拟环境：

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

# 2. 一键安装所有依赖
pip install -r requirements.txt
```

> requirements.txt 内容：
> ```
> paramiko
> fastapi
> pydantic
> uvicorn
> openai
> ```

如需手动逐条安装：

```bash
pip install fastapi uvicorn paramiko "openai>=1.0.0" pydantic
```

配置

首次启动时，如果找不到 PwnPilot_config.json，会进入交互式配置向导并生成该文件。

你也可以手动创建 PwnPilot_config.json（与 PwnPilot.py 同目录）：

```json
{
  "LANGUAGE": "zh",
  "API_KEY": "你的API_KEY",
  "BASE_URL": "https://你的服务地址/v1",
  "MODEL_NAME": "你的模型名称",
  "KALI_HOST": "127.0.0.1",
  "KALI_PORT": 22,
  "KALI_USER": "root",
  "KALI_PASS": "你的SSH密码",
  "SESSIONS_DIR": "sessions"
}
```

说明：

- LANGUAGE：zh 或 en
- BASE_URL：例如 https://api.deepseek.com/v1（按你的服务商要求填写）
- SESSIONS_DIR：会话存储目录，默认 sessions

 启动
```bash
python PwnPilot.py
```

然后在浏览器打开：

- http://127.0.0.1:8000

默认只监听 127.0.0.1，面向本机使用。

使用方式

- 右侧终端：直接输入键盘操作，会通过 /ws/terminal 转发到 SSH PTY（ai也可以直接使用kali）
- 左侧对话：
  - 选择或创建一个会话后，在输入框发送指令
  - 后端会把“你的指令 + 最新终端回显片段”提供给代理，代理再决定是否向终端输入命令
  - 输入包含 停 或 stop 会中止当前自动循环

会话数据会写入 SESSIONS_DIR 下的 jsonl 文件：

- 第一行是会话 meta（id/title/created_at）
- 后续每行是对话消息（role/content）

重要注意事项（安全与边界）
- 本项目会保存会话历史与终端回显到本地磁盘。不要在终端里输出不应落盘的敏感信息。
- 配置文件会包含 API_KEY 与 SSH 密码（明文）。请自行做好本机权限控制，例如把文件权限改为仅当前用户可读写。
- 当前实现是“全局单 PTY”：所有会话共享同一个 SSH 终端通道。会话更像“记录与上下文”，不是隔离的执行环境。
- 仅建议在你完全授权的环境使用。你需要对终端里执行的任何操作负责。

已知限制
- 终端输出的“稳定判断”是基于短时间内输出长度不再变化的启发式策略，遇到持续刷新的交互程序可能会截断或等待不准确。
- 断线重连、取消任务后的状态复位，目前实现偏简化，复杂场景可能出现状态不同步。

许可与免责声明
- 本项目仅用于你授权的系统管理与实验环境自动化。任何超出授权范围的使用都不在本项目作者责任范围内。