# 🚀 Codex Professional Agent

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Ollama](https://img.shields.io/badge/AI-Ollama-orange)

Codex Professional Agent is a fully autonomous, local AI software engineer. Powered by local LLMs via [Ollama](https://ollama.com/), it doesn't just generate text: **it reasons, executes system commands, reads/writes files, searches the web, and fixes its own bugs.**

Think of it as your personal, open-source, local alternative to Devin or GitHub Copilot Workspace, running entirely on your machine with zero API costs and 100% privacy.

---

## ✨ Key Features

*   🧠 **Autonomous ReAct Loop:** The agent uses a *Reason + Act* loop. It can chain multiple actions together (e.g., scan a directory $\rightarrow$ read a file $\rightarrow$ write a fix $\rightarrow$ run a test).
*   💻 **Native Terminal Execution:** Executes PowerShell and Git commands directly on your machine.
*   📂 **Advanced File Management:** Reads and writes code, configurations, and even 3D models (`.obj`, `.stl`, `.scad`).
*   🌐 **Web Browsing & Scraping:** Uses DuckDuckGo to search for solutions and can scrape full web documentation URLs to learn new APIs on the fly.
*   🔄 **Auto-Healing:** If a command or script fails, the agent intercepts the error output and automatically tries an alternative solution without user intervention.
*   💾 **Long-Term Memory:** Can remember specific project rules, server IPs, or preferences across different sessions.
*   🌍 **Multilingual:** UI and AI reasoning fully support English, Italian, Spanish, and French.
*   📥 **Built-in Model Manager:** Download, switch, or delete Ollama models directly from the UI.

---

## 🛠️ Built-in Tools

The agent natively understands and utilizes the following tools:
*   `exec_cmd`: Runs PowerShell/Git commands.
*   `list_dir`: Scans local directories.
*   `read_file` / `create_file`: Reads existing files or creates new ones.
*   `web_search`: Searches the web for up-to-date knowledge.
*   `read_url`: Extracts clean text from documentation pages.
*   `save_memory`: Stores persistent facts in its local database.

---

## 🚀 Installation (One-Click Setup)

This project is designed for Windows and requires zero manual configuration. 

1. **Clone or Download** this repository.
2. Double-click the **`Setup_Codex.bat`** file.
3. The setup will automatically:
   * Install required Python dependencies (`pywebview`, `requests`, `beautifulsoup4`).
   * Check for Ollama (and install it if missing).
   * Ask you which starting AI model you want to use (e.g., `qwen2.5-coder:14b`).
   * Download the model.
   * Create a handy shortcut on your Desktop.
4. Launch the app from the Desktop shortcut!

### Prerequisites (If installing manually)
* Python 3.8+
* [Ollama](https://ollama.com/) installed and running in the background.

---

## 💻 Recommended Hardware & Models

Since this runs 100% locally, your hardware dictates the speed and intelligence of the agent.

| Model | Recommended For | VRAM Requirement |
| :--- | :--- | :--- |
| **`qwen2.5-coder:1.5b/3b`** | Low-end PCs, basic scripting | 4GB - 6GB VRAM |
| **`llama3.1:8b`** / **`qwen2.5-coder:7b`**| Fast, everyday coding and tasks | 8GB VRAM (e.g., RTX 3060/4060) |
| **`qwen2.5-coder:14b`** | **Optimal!** Complex autonomous tasks | 16GB VRAM (e.g., RTX 4080) |
| **`devstral:24b`** | Heavy SWE benchmark tasks | 24GB VRAM (e.g., RTX 4090) |

*Note: You can easily download and manage these models directly from the app's Settings menu.*

---

## 🎨 Interface Highlights

*   **Dark Mode UI:** Modern, clean interface inspired by top-tier IDEs.
*   **Markdown & Syntax Highlighting:** Beautifully rendered code blocks with 1-click copy.
*   **Live Action Badge:** See exactly what the agent is doing in the background (e.g., "⚡ Terminal...", "📖 Reading file...").
*   **Session Management:** Save, rename, and resume previous chats from the sidebar.

---

## 🛡️ Security Warning

**Use with caution.** This agent is designed to execute commands on your local system via PowerShell. 
* Do not leave the agent running completely unsupervised on critical production machines.
* It has the capability to delete files and modify your system if instructed to do so.
* The application runs locally; no data or code is sent to third-party cloud servers (unless you specifically connect it to a remote Ollama instance in the settings).

---

## 🤝 Contributing

Feel free to fork this project, submit pull requests, or open an issue if you find bugs or have feature requests. Let's build the ultimate open-source local AI agent together!

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).