PwnPilot (Local SSH Shared Terminal + LLM Collaboration Console)

A local web console: the left panel is the session list and chat area, while the right panel is a shared interactive terminal (PTY) connected to a remote host via SSH. The backend uses a large language model to loop "chat instructions + terminal output" into a continuous cycle, enabling automated operations and human-AI collaboration in environments you have explicitly authorized.

Features

- In-browser terminal (xterm.js) with real-time SSH interactive shell output
- Human and automated agent share the same terminal (shared input/output on a single screen)
- Session management: create/delete sessions, persistent chat and output per session
- Bilingual UI (Chinese/English, controlled by the LANGUAGE config option)
- LLM invocation via OpenAI-compatible API (AsyncOpenAI + base_url)

Requirements

- Python 3.10+ (3.11 recommended)
- A local browser (Chrome / Edge / Firefox)
- A host accessible via SSH (your own machine or lab environment) with an interactive shell
- An API compatible with OpenAI Chat Completions (supporting base_url and model parameters)

Installation

It is recommended to use a virtual environment:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

# 2. Install all dependencies in one command
pip install -r requirements.txt
```

> Contents of requirements.txt:
> ```
> paramiko
> fastapi
> pydantic
> uvicorn
> openai
> ```

To install manually one by one:

```bash
pip install fastapi uvicorn paramiko "openai>=1.0.0" pydantic
```

Configuration

On the first launch, if PwnPilot_config.json is not found, an interactive setup wizard will run and generate the file.

You can also manually create PwnPilot_config.json (in the same directory as the script):

```json
{
  "LANGUAGE": "en",
  "API_KEY": "your-api-key",
  "BASE_URL": "https://your-service-url/v1",
  "MODEL_NAME": "your-model-name",
  "KALI_HOST": "127.0.0.1",
  "KALI_PORT": 22,
  "KALI_USER": "root",
  "KALI_PASS": "your-ssh-password",
  "SESSIONS_DIR": "sessions"
}
```

Notes:

- LANGUAGE: "zh" or "en"
- BASE_URL: e.g. https://api.deepseek.com/v1 (fill in according to your service provider's requirements)
- SESSIONS_DIR: directory for storing sessions, defaults to "sessions"

Launch

```bash
python PwnPilot.py
```

Then open in your browser:

- http://127.0.0.1:8000

By default it only listens on 127.0.0.1, intended for local use.

Usage

- Right-side terminal: keyboard input is forwarded directly to the SSH PTY via /ws/terminal (the AI can also interact with the terminal directly)
- Left-side chat panel:
  - After selecting or creating a session, send instructions via the input box
  - The backend provides "your instruction + the latest terminal output snippet" to the agent, which then decides whether to issue commands to the terminal
  - Typing "stop" or "停" will halt the current autonomous loop

Session data is written as jsonl files under SESSIONS_DIR:

- The first line is session metadata (id/title/created_at)
- Each subsequent line is a chat message (role/content)

Important Notes (Security & Boundaries)

- This project saves chat history and terminal output to local disk. Do not output sensitive information in the terminal that should not be persisted.
- The configuration file contains API_KEY and SSH password in plaintext. Restrict file permissions accordingly (e.g. read/write for the current user only).
- The current implementation uses a single global PTY: all sessions share the same SSH terminal channel. Sessions function more as "records and context" rather than isolated execution environments.
- Only use this in environments you have fully authorized. You are responsible for any operations executed in the terminal.

Known Limitations

- Terminal output "stability detection" relies on a heuristic based on output length remaining constant over a short period. Interactive programs with continuous refreshing may result in truncation or inaccurate timing.
- Reconnection after disconnects and state reset after task cancellation are currently simplified; complex scenarios may lead to state desynchronization.

License & Disclaimer

- This project is intended solely for system administration and lab environment automation that you have authorized. The author bears no responsibility for any use beyond authorized scope.
