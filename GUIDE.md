# Personal Desktop Assistant — Complete Guide

## File Structure

```
PersonalAssistant/
│
├── app/
│   ├── __init__.py
│   ├── main.py                        ← FastAPI app factory + static mount
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                  ← All HTTP endpoints
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── intent.py                  ← ASK / PREPARE / ACT classifier
│   │   ├── planner.py                 ← Deterministic keyword planner (original)
│   │   ├── llm_planner.py             ← NEW Phase 7: Ollama LLM planner
│   │   └── safety.py                  ← Risk scoring for every step and plan
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                 ← All Pydantic data models
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── assistant_service.py       ← UPDATED Phase 7: orchestration layer
│   │   ├── local_model.py             ← Ollama status checker
│   │   ├── session_store.py           ← Save/load sessions to data/sessions/
│   │   └── tool_registry.py           ← UPDATED Phase 7: routes steps to tools
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── desktop_actions.py         ← click, type, hotkey, file ops
│   │   ├── document_reader.py         ← read txt/md/pdf/docx/pptx/xlsx/csv
│   │   ├── file_search.py             ← search Desktop/Documents/Downloads
│   │   ├── screen_inspector.py        ← active window, UIA controls, OCR
│   │   └── screenshot_tool.py         ← NEW Phase 7: capture + vision description
│   │
│   └── ui/
│       ├── static/
│       │   ├── app.js                 ← UPDATED Phase 7: chat-history UI
│       │   └── styles.css             ← UPDATED Phase 7: dark sidebar layout
│       └── templates/
│           └── index.html             ← UPDATED Phase 7: sidebar + chat layout
│
├── tests/
│   ├── test_desktop_actions.py
│   ├── test_local_model.py
│   ├── test_planner.py
│   └── test_screen_inspector.py
│
├── data/
│   └── sessions/                      ← auto-created; one JSON file per session
│
├── .gitignore
├── README.md
├── ahead.md
└── requirements.txt
```

---

## How It Works

### The Big Picture

The assistant runs as a local web server. You open http://127.0.0.1:8000 in your browser, type a plain-English instruction, and the assistant:

1. Classifies your intent (read-only vs action)
2. Plans what it would do (a list of tool steps)
3. Scores risk for every step and the whole plan (0-100)
4. Previews everything before touching anything
5. Waits for your confirmation on anything that changes state
6. Executes only after you approve

Nothing is ever executed without you seeing a plan first.

---

### Layer by Layer

#### 1. HTTP Layer — app/api/routes.py

| Endpoint | What it does |
|---|---|
| GET / | Serves the browser UI |
| GET /health | Simple liveness check |
| GET /api/model/status | Ollama connectivity status |
| GET /api/llm/status | Whether LLM or deterministic planner is active |
| POST /api/request | Submit an instruction — returns plan + observations |
| POST /api/confirm | Approve or reject the pending plan |
| GET /api/screenshot | Take a screenshot right now (no disk write) |

---

#### 2. Planning Layer — app/core/

**intent.py**
Looks at your text for read-only words (find, show, summarize) vs write words (open, copy, rename, click). Returns ASK, PREPARE, or ACT. This affects whether the plan auto-executes or waits for confirmation.

**llm_planner.py** (new in Phase 7)
When Ollama is configured, sends your instruction to the local model with a system prompt that says "return a JSON array of tool calls". Parses the response and builds a proper Plan from it. If Ollama is down, times out, or returns garbage, it falls through to planner.py silently — zero breakage.

**planner.py** (original deterministic planner)
Uses keyword matching and regex to build a plan without any model. Handles: file search, document read, app open, file copy/move/rename, screen inspect, desktop click/type/hotkey. Always available as fallback.

**safety.py**
Every PlanStep gets a risk score:

- File search / document read → 10 (low, read-only)
- File copy/move/rename with explicit paths → 50-55 (medium)
- App open → 45 (medium)
- Desktop click/type/hotkey → 82-92 (high)
- File delete → 95 (high, blocked in V1)
- Missing parameters on any action → score pushed to 92

A plan score is the max step score + 5 if there are multiple steps. Any score >= 40 requires confirmation.

---

#### 3. Service Layer — app/services/

**assistant_service.py** (updated in Phase 7)
The main orchestrator. When you submit a request it calls LLMPlanner.build_plan(), loops over steps calling tool_registry.inspect() to get a safe preview, and if a screen_inspect step is in the plan also runs ScreenshotTool.capture(). Assembles all observations into the reply. Auto-executes read-only ASK plans; holds ACT plans for confirmation.

When you confirm, calls tool_registry.execute() on each step, updates step statuses, and saves the result to the session store.

**session_store.py**
Each request creates an ActionSession saved as a JSON file under data/sessions/. Used to retrieve the pending plan when you hit Confirm.

**local_model.py**
Checks whether Ollama is running, whether the configured model is installed, and refuses non-localhost endpoints.

**tool_registry.py** (updated in Phase 7)
Routes each PlanStep to the right tool. Two modes: inspect() for preview (no side effects) and execute() for real execution. Also integrates the screenshot tool into screen_inspect steps.

---

#### 4. Tools Layer — app/tools/

**file_search.py**
Recursively searches ~/Desktop, ~/Documents, ~/Downloads for files matching your query by name. Returns up to 5 matches.

**document_reader.py**
Opens a file and returns a text preview. Supported: .txt .md .py .json .csv .pdf .docx .pptx .xlsx. Uses pypdf, python-docx, openpyxl, python-pptx.

**screen_inspector.py**
Uses ctypes (Windows) to get the active window title, handle, process ID, and bounds. Optionally uses pywinauto to list visible UI controls via Windows UI Automation, and pytesseract + Pillow for OCR. Works on Windows only; gracefully reports unavailable elsewhere.

**desktop_actions.py**
The action engine. Uses pyautogui for mouse/keyboard actions. All actions require explicit parameters:

- desktop_click — click by x, y coordinates
- desktop_click_target — resolve a visible UI control by label text using pywinauto, then click its center point
- desktop_type — type quoted text into the currently focused control
- desktop_type_target — resolve a visible field by label, click to focus, then type
- desktop_hotkey — press a key combination like ctrl+s
- app_open — os.startfile() after checking the path exists
- file_copy / file_move / file_rename — uses shutil; refuses overwrites; requires explicit quoted paths; delete is intentionally blocked

**screenshot_tool.py** (new in Phase 7)
Captures a PNG in memory using Pillow.ImageGrab. Never writes to disk. If a vision-capable Ollama model (llava) is configured, sends the base64 PNG to it and returns a natural-language description of what is visible on screen.

---

#### 5. Data Models — app/models/schemas.py

| Model | Purpose |
|---|---|
| UserRequest | {text, mode} from the browser |
| PlanStep | One action: tool, target, risk score, metadata, status |
| Plan | List of steps + overall risk assessment |
| RiskAssessment | Score 0-100, level, reasons, requires_confirmation flag |
| ActionSession | Full record: request + plan + observations + result |
| AssistantReply | What the browser receives after each request |
| ConfirmationRequest | {session_id, approved} from the confirm button |
| ExecutionResult | {success, message, details[]} from each tool |

---

#### 6. UI Layer — app/ui/

A single-page app with no frontend framework.

**Sidebar** — planner mode badge (LLM / Deterministic), quick-example buttons, safety notes.

**Chat history** — every request becomes a user bubble + assistant bubble. The assistant bubble contains: summary, risk bar with reasons, plan step cards with status pills, collapsible observations, inline confirmation buttons per turn, and the execution result once it runs.

**Input area** — textarea + mode selector + Send button with loading spinner. Enter submits; Shift+Enter adds a newline.

---

## How to Start

### Prerequisites

- Python 3.11 or 3.12
- Windows recommended (screen inspection and desktop actions are Windows-only; the server itself runs anywhere)

### First-time setup

```powershell
cd D:\DEV\PersonalAssistant

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Start the server

```powershell
python -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

### Optional dependencies

Install these for full capability:

```powershell
# Screen capture + OCR
pip install pillow pytesseract

# Windows UI Automation (needed for click "Save" and type "x" into "Field")
pip install pywinauto

# Desktop mouse and keyboard control
pip install pyautogui

# PDF reading
pip install pymupdf
```

OCR also requires the Tesseract binary on your PATH:
https://github.com/UB-Mannheim/tesseract/wiki

### Enable the LLM planner (optional)

Install Ollama from https://ollama.com then pull a model:

```powershell
ollama pull llama3.1
ollama pull llava        # optional: vision model for screen description
```

Set environment variables before starting the server:

```powershell
$env:LOCAL_MODEL_PROVIDER    = "ollama"
$env:LOCAL_MODEL_NAME        = "llama3.1"
$env:LOCAL_VISION_MODEL_NAME = "llava"
$env:LOCAL_MODEL_ENDPOINT    = "http://127.0.0.1:11434"

python -m uvicorn app.main:app --reload
```

The sidebar badge turns blue and shows "LLM · llama3.1". Without those variables it stays green "Deterministic" and everything works the same.

### Run the tests

```powershell
python -m pytest tests -p no:cacheprovider
```

---

## Example Instructions

Read-only (no confirmation needed):

```
Find my latest report and summarize it
What is on my screen right now?
Search for budget in my Documents
```

File actions (confirmation required):

```
Copy "C:\temp\notes.txt" to "C:\temp\notes_backup.txt"
Rename "C:\temp\old.txt" to "new.txt"
Open C:\Users\Me\Documents\report.pdf
```

Desktop actions (confirmation required):

```
click x=420 y=260
click "Save"
type "Hello World"
type "Piyush" into "Name"
press "ctrl+s"
press "alt+f4"
```

---

## Safety Rules

- Every file operation and desktop action requires confirmation before it runs
- The full plan, risk score, and risk reasons are shown before any confirmation prompt
- File delete is intentionally blocked in V1
- File overwrites are refused
- Target-text clicks and typed-into-field actions refuse to execute if the UI control cannot be resolved by Windows UI Automation
- Non-localhost model endpoints are refused — only 127.0.0.1 and localhost are accepted
- Screenshots are captured in memory and never saved to disk by default
- PyAutoGUI failsafe is enabled — moving the mouse to a screen corner aborts any pointer action

---

## What Each Phase Added

| Phase | What was built |
|---|---|
| 1 | Core scaffold: intent, planner, safety, session store, browser UI |
| 2 | File copy, move, rename with quoted paths; overwrite protection; chain risk reasons |
| 3 | Screen inspection: active window metadata, UIA control listing, OCR via Tesseract |
| 4 | Desktop actions: click by coordinates, type into focused control, hotkeys via pyautogui |
| 5 | Target-text click: resolve visible UI control by label before clicking |
| 6 | Target-text type: resolve visible field by label, focus it, then type |
| 7 | LLM planner via Ollama; screenshot + vision description; dark chat UI with sidebar |
