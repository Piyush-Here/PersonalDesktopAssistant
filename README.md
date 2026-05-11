# Personal Desktop Assistant

> A Windows-first, confirmation-first local AI assistant that inspects your screen, reads your files, and executes desktop actions — but only after you approve every step.

<!-- DEMO: replace this line with your demo GIF/screenshot once recorded -->
<!-- ![Demo](docs/demo.gif) -->

**[▶ Watch the demo](#)** &nbsp;·&nbsp; **[Quick start](#quick-start)** &nbsp;·&nbsp; **[Capabilities](#capabilities)**

---

## What it does

You type a plain-English instruction. The assistant:

1. **Classifies** your intent (read-only vs. state-changing)
2. **Plans** a sequence of tool steps
3. **Risk-scores** each step from 0–100
4. **Previews** everything — nothing runs yet
5. **Waits** for your confirmation on any action that changes state
6. **Executes** only after you approve

Nothing is ever executed without you seeing the plan and risk score first.

---

## Quick start

```powershell
# Clone and enter the project
cd PersonalAssistant

# One-command setup (creates venv + installs all deps)
.\setup.ps1

# Start the server
.\run.ps1

# Open in browser
start http://127.0.0.1:8000
```

**With Ollama LLM planner (optional):**
```powershell
.\run.ps1 -llm -model llama3.1
```

**Create demo files (needed for Demo 1 and Demo 2):**
```powershell
python demo_setup.py
```

---

## Capabilities

| Feature | Status | Notes |
|---|---|---|
| Natural language intent classification | ✅ Core | Always on |
| Deterministic action planner | ✅ Core | Always on, no LLM needed |
| Risk scoring (0–100) per step | ✅ Core | Always on |
| Confirmation gate for all writes | ✅ Core | Cannot be bypassed |
| File search (Desktop, Documents, Downloads) | ✅ Core | |
| Document reading (.txt .md .csv .pdf .docx .pptx .xlsx) | ✅ Core | |
| Session logging (local JSON) | ✅ Core | |
| Screen inspection (active window metadata) | ✅ Core (Windows) | Via ctypes |
| Screenshot capture | ✅ Optional | `pip install pillow` |
| Hotkey / keyboard automation | ✅ Optional | `pip install pyautogui` |
| Mouse click by coordinates | ✅ Optional | `pip install pyautogui` |
| UI element click by visible text | ✅ Optional | `pip install pywinauto` |
| Typed input into named UI field | ✅ Optional | `pip install pywinauto` |
| OCR text extraction from screen | ✅ Optional | `pip install pytesseract` + Tesseract binary |
| LLM planner (Ollama) | ✅ Optional | Set `LOCAL_MODEL_PROVIDER=ollama` |
| Vision model screen description (llava) | ✅ Optional | Ollama + llava model |

---

## Three demo flows

### Demo 1 — Find and read a document (read-only, no confirmation needed)
```
Find my budget report and summarize it
```
Shows: intent classification → file search → document read → automatic execution → result.

### Demo 2 — File copy with confirmation gate
```
Copy "C:\Users\Me\Documents\notes.txt" to "C:\Users\Me\Desktop\notes_backup.txt"
```
Shows: plan preview → risk score (MEDIUM) → step cards → Confirm button → execution result.

### Demo 3 — Screen inspect + hotkey (requires pillow + pyautogui)
```
What is on my screen right now?
press "ctrl+s"
```
Shows: active window inspection → screenshot observation → desktop action → HIGH risk confirmation → Save dialog appears.

---

## Project structure

```
app/
├── api/routes.py          ← HTTP endpoints
├── core/
│   ├── intent.py          ← ASK / PREPARE / ACT classifier
│   ├── planner.py         ← Deterministic keyword planner
│   ├── llm_planner.py     ← Ollama LLM planner (opt-in)
│   └── safety.py          ← Risk scoring (0–100)
├── services/
│   ├── assistant_service.py  ← Orchestration layer
│   ├── local_model.py        ← Ollama status checker
│   ├── session_store.py      ← Local JSON session log
│   └── tool_registry.py      ← Routes steps to tools
├── tools/
│   ├── file_search.py        ← Search Desktop/Documents/Downloads
│   ├── document_reader.py    ← Read txt/md/pdf/docx/pptx/xlsx/csv
│   ├── screen_inspector.py   ← Active window + UIA + OCR
│   ├── screenshot_tool.py    ← In-memory screenshot + vision
│   └── desktop_actions.py    ← Click/type/hotkey/file ops
└── ui/                       ← Single-page browser frontend
```

---

## Safety design

- Every file and desktop action requires confirmation after risk review
- The full plan, risk score, and risk reasons are shown before any confirmation prompt
- File delete is intentionally blocked in V1
- File overwrites are refused
- Target-text clicks refuse to execute if the UI control cannot be resolved
- Non-localhost model endpoints are refused — only 127.0.0.1 and localhost accepted
- Screenshots are captured in memory and never saved to disk by default
- PyAutoGUI failsafe is enabled — move mouse to screen corner to abort any pointer action

---

## Optional Ollama setup

```powershell
# Install Ollama from https://ollama.com
ollama pull llama3.1           # text planner
ollama pull llava              # optional: vision model for screen description

# Start with LLM planner
.\run.ps1 -llm -model llama3.1
```

The sidebar badge turns blue when the LLM planner is active. Without the env vars it stays green (Deterministic) and everything works the same.

---

## Testing

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest tests -p no:cacheprovider -v
```

Expected: **24 tests passing**.

---

## Known limitations

- **Scope**: V1 targets explicit, bounded instructions. Ambiguous or complex multi-step goals may not plan correctly without the optional LLM planner configured.
- **Desktop automation**: Target-text UI actions depend on the target application exposing controls via Windows Accessibility APIs. Applications with elevated privileges or custom UI frameworks may not be supported.
- **OCR**: Requires the Tesseract OCR engine installed separately as a binary. The `pytesseract` Python package alone is not sufficient.
- **Platform**: Screen inspection and desktop automation require Windows. The FastAPI server and file tools run on any platform.
- **File search scope**: Searches Desktop, Documents, and Downloads only. Files in other locations require an explicit full path.
- **LLM planning**: Opt-in. Requires a locally running Ollama instance. The deterministic planner is the default and works without any model infrastructure.
- **Concurrency**: The session store is single-threaded in V1. Not designed for concurrent multi-user use.

---

## Roadmap

- [ ] Multi-step chain approval (open Notepad → type → save as one confirmed chain)
- [ ] Before/after screenshot diff displayed after action execution
- [ ] Browser automation via Playwright
- [ ] Window management (focus, minimize, maximize, switch)
- [ ] Richer natural-language parsing beyond deterministic keyword matching
- [ ] PyInstaller / NSIS packaging with a desktop shortcut

---

## Built with

Python 3.12 · FastAPI · Pydantic v2 · Jinja2 · pyautogui · pywinauto · Pillow · PyMuPDF · python-docx · openpyxl · python-pptx
