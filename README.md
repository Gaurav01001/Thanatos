<div align="center">

# ⚡ Thanatos
**Autonomous, Local AI Desktop Assistant ("Jarvis") for Windows**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Windows 10/11](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![100% Local](https://img.shields.io/badge/Privacy-100%25%20Local%20%26%20Private-success)](https://github.com/Gaurav01001/Thanatos)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*100% private. Runs offline on your hardware. Zero subscriptions.*

</div>

---

## ⚡ 1-Click Install

Open **PowerShell** (Run as Administrator) and run:

```powershell
irm https://raw.githubusercontent.com/Gaurav01001/Thanatos/main/install.ps1 | iex
```

> Auto-installs Python, Ollama models (`qwen2.5-coder:7b`), Piper TTS voice, and sets up a global `thanatos` command + Desktop shortcut.

---

## ⌨️ Controls & Hotkeys

| Shortcut / Trigger | Action |
| :--- | :--- |
| <kbd>Ctrl</kbd> + <kbd>Space</kbd> | **Toggle Floating Mini-Deck HUD** (expandable chat card) |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd> | **Clipboard Smart Fix** (auto-detects code/JSON bugs, fixes & replaces clipboard) |
| <kbd>F8</kbd> | **Socratic DSA Mentor** (captures screen problem, hints at approach & complexity) |
| Say *"Wake up"* | Start hands-free voice mode |
| Say *"Go to sleep"* | Return to silent standby mode |
| Drag Bottom-Right `◢` | Resize HUD (remembers size, locked at min 340×240) |
| Click `📄` Paperclip | Index documents (PDF, code, notes) into local Hybrid RAG |
| Click `🔊` / Type `/mute` | Toggle audio mute |
| Type `exit` | Safely shutdown assistant |

---

## 🌟 Features

* **Dual-Track Voice & Audio**: Detailed markdown/code on-screen; 1-sentence spoken punchline via offline Piper TTS (WASAPI 48kHz, zero lag).
* **Clipboard Intelligence**: Copy broken code or JSON, hit <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>V</kbd>, and paste the clean fix immediately.
* **Grounded Live Web Synthesis**: Ask for recommendations or prices (e.g. *"suggest a winter perfume under 3000 rupees"*); fetches real web snippets in background with zero browser popups.
* **3-Tier SQLite Memory**: Remembers your name, tech stack, and notes across sessions locally (`data/user_memory.db`).
* **Socratic Vision Mentor**: Analyzes coding problems on screen (<kbd>F8</kbd>) without spoiling direct code.
* **Autonomous Browser**: Playwright Chromium automation for explicit web tasks (*"open browser and search for..."*).
* **Hybrid RAG Engine**: Qdrant dense vector search + BM25 keyword matching + Cross-Encoder reranking for local files.

---

## 💾 Storage & Requirements

### Disk Usage
* **Source & App Files**: ~135 MB
* **Python Environment (`.venv`)**: ~5.2 GB (PyTorch, Playwright, Piper)
* **Local LLM (`qwen2.5-coder:7b`)**: ~4.7 GB
* **Offline Voice Model**: ~60 MB
* **Total Footprint**: **~10.5 GB** *(100% local, no cloud fees)*

### Requirements
* **OS**: Windows 10 / 11 (64-bit)
* **RAM**: 16 GB recommended (8 GB minimum)
* **Hardware**: Multi-core CPU or NVIDIA GPU (CUDA supported)

---

## 🛠️ Manual Setup (Developers)

```powershell
# 1. Clone
git clone https://github.com/Gaurav01001/Thanatos.git
cd Thanatos

# 2. Venv & Dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium

# 3. Pull Ollama Model
ollama pull qwen2.5-coder:7b

# 4. Download Voice File
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx" -OutFile "en_US-ryan-medium.onnx"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json" -OutFile "en_US-ryan-medium.onnx.json"

# 5. Launch
python -m engine
```

---

## 🩺 Diagnostics & Testing

```powershell
# Run health check (Ollama, SQLite, Piper TTS, Playwright)
thanatos --check

# Run test suite (81 tests)
pytest
```

---

## 📄 License

MIT License. Free to use, modify, and distribute.
