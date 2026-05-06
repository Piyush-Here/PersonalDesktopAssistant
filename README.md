# Personal Desktop Assistant

A Windows-first, confirmation-first local assistant that can inspect accessible content, propose actions, and execute only after user approval.

## V1 capabilities

- Natural language request intake
- Intent classification into ask/prepare/act
- Action planning with confirmation gates
- Local file search
- Document reading for `txt`, `md`, `pdf`, `docx`, `pptx`, `xlsx`, `csv`
- Session logging
- Minimal browser UI for chat, plan preview, and confirmation

## Phase 2 capabilities

- Quoted source and destination parsing for file copy, move, and rename requests
- Exact file-operation previews before confirmation
- Confirmed execution for copy, move, and rename
- Overwrite protection for file operations
- Chain-level risk score and risk reasons before approval
- Local model provider boundary with deterministic fallback

## Phase 3 capabilities

- Read-only active window metadata inspection on Windows
- In-memory screenshot availability check
- Optional local OCR text preview through Tesseract
- Optional Windows UI Automation control listing through pywinauto

## Phase 4 capabilities

- Confirmed desktop click by explicit screen coordinates
- Confirmed typing of explicit quoted text into the focused control
- Confirmed key or hotkey press by explicit key names
- PyAutoGUI failsafe enabled for pointer actions

## Phase 5 capabilities

- Resolve visible UI controls by quoted text through Windows UI Automation
- Preview the matched control type, bounds, and click point before approval
- Refuse target-text clicks when no exact visible target can be resolved

## Phase 6 capabilities

- Resolve visible UI fields by quoted text before typing
- Preview the matched field/control bounds and focus point before approval
- Click the resolved field and type explicit text only after confirmation
- Refuse targeted typing when no exact visible target can be resolved

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Local model mode

The assistant defaults to the deterministic local planner. To connect a local Ollama model, set:

```powershell
$env:LOCAL_MODEL_PROVIDER="ollama"
$env:LOCAL_MODEL_NAME="llama3.1"
$env:LOCAL_MODEL_ENDPOINT="http://127.0.0.1:11434"
```

Only localhost model endpoints are accepted. Non-local model URLs are refused.

## Screen observation mode

Screen inspection is local and read-only. Screenshot data is inspected in memory and is not saved by the assistant.

Optional adapters:

- `pillow` enables screenshot capture.
- `pywinauto` enables Windows UI Automation control discovery.
- `pytesseract` enables OCR when the local Tesseract engine is installed and available on PATH.

## Desktop action mode

Desktop actions are write-capable and always require confirmation after risk review.

Supported explicit forms:

```text
click x=420 y=260
click "Save"
type "hello world"
type "Piyush" into "Name"
press "ctrl+s"
```

For target-text clicks and targeted typing, the assistant inspects visible UI Automation controls in the active window and proposes the exact click or focus point before confirmation. It does not execute if the target cannot be resolved.

## Notes

- The current V1 is deterministic and local-first. It does not depend on an LLM yet.
- `app_open` can execute after confirmation when the target path exists.
- Any state-changing chain requires user confirmation after the risk score is shown.
- File delete and inferred write-capable UI automation are intentionally staged and not fully enabled yet.
- File copy, move, and rename require explicit quoted paths, for example `copy "C:\source.txt" to "C:\target.txt"`.

## Next engineering steps

- Add real Windows UI Automation and OCR adapters
- Add Playwright browser automation
- Add a tool-calling LLM layer for stronger intent extraction
- Add broader natural-language file-operation parsing beyond quoted paths
