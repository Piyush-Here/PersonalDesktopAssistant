# Personal Desktop Assistant - Current State and Roadmap

## What It Does Now

This project is a Windows-first, local-first personal desktop assistant scaffold. It accepts English instructions, builds a plan, calculates risk, previews what it intends to do, and requires user confirmation before any state-changing action runs.

Current capabilities:

- Takes natural language requests through a browser UI.
- Classifies requests into ask, prepare, and act modes.
- Builds deterministic plans without needing a cloud model.
- Shows a chain-level risk score from 0 to 100 with risk reasons.
- Stores sessions locally under `data/sessions`.
- Searches common local folders: Desktop, Documents, Downloads.
- Reads and previews supported documents: `txt`, `md`, `pdf`, `docx`, `pptx`, `xlsx`, `csv`.
- Opens a local file or app after confirmation when the target path exists.
- Copies, moves, and renames files after confirmation using explicit quoted paths.
- Refuses file overwrites.
- Keeps file delete blocked.
- Reports local model status and refuses non-local model endpoints.
- Supports optional localhost Ollama configuration.
- Inspects the active Windows screen where permissions allow:
  - active window title
  - window handle
  - process id
  - bounds
  - screenshot availability
  - visible UI Automation controls
  - OCR preview through local Tesseract when installed
- Executes explicit desktop actions after confirmation:
  - `click x=420 y=260`
  - `click "Save"`
  - `type "hello world"`
  - `type "Piyush" into "Name"`
  - `press "ctrl+s"`
- Resolves visible UI controls by quoted text using Windows UI Automation before clicking or typing.
- Refuses UI target actions when no exact visible target can be resolved.

The assistant is not yet fully autonomous. It can observe, preview, and perform bounded actions, but it still depends on deterministic parsing and explicit user instructions.

## How To Run

From the project root:

```powershell
cd D:\DEV\JavaDevloperStack\Projects\PersonalAssistant
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

Model status:

```text
http://127.0.0.1:8000/api/model/status
```

## Optional Local Model Setup

The default planner is deterministic and fully local.

To point the assistant at a local Ollama model:

```powershell
$env:LOCAL_MODEL_PROVIDER="ollama"
$env:LOCAL_MODEL_NAME="llama3.1"
$env:LOCAL_MODEL_ENDPOINT="http://127.0.0.1:11434"
python -m uvicorn app.main:app --reload
```

Only localhost endpoints are accepted. Remote model URLs are intentionally refused.

## Testing

Run:

```powershell
python -m pytest tests -p no:cacheprovider
```

Current verified state:

```text
24 tests passing
```

The `-p no:cacheprovider` flag avoids pytest cache writes, which have caused permission issues in this Windows workspace.

## Important Runtime Notes

- Screen access and desktop automation work best when the app runs in the normal interactive Windows desktop session.
- Background or sandboxed runs may not see the active window or screen pixels.
- OCR requires the local Tesseract engine installed and available on PATH, not just the `pytesseract` Python package.
- PyAutoGUI has failsafe enabled. Moving the mouse to a screen corner can abort pointer automation.
- UI Automation visibility depends on the target app exposing controls through Windows accessibility APIs.

## Safety Rules Already In Place

- Any file or desktop state change requires confirmation.
- The UI shows risk score and risk reasons before confirmation.
- File delete is blocked.
- File operations require explicit paths.
- File overwrites are refused.
- Desktop target clicks and targeted typing require exact visible target resolution.
- Non-local model endpoints are refused.

## Future Steps

### 1. Real Local LLM Planning

- Add a tool-calling planner backed by a local model.
- Convert English instructions into structured tool calls.
- Keep deterministic planner as fallback.
- Validate every model-generated tool call against schemas before execution.
- Add model output repair and refusal handling.

### 2. Stronger Observation Layer

- Improve active-window observation with process name and executable path.
- Add richer UI Automation tree snapshots.
- Add OCR region support instead of whole-screen OCR only.
- Add screenshot thumbnails in the UI without saving images by default.
- Add coordinate mapping between screenshot, OCR boxes, and UIA controls.

### 3. Better Target Resolution

- Resolve controls by role plus label, for example `button "Save"` or `textbox "Email"`.
- Rank multiple matches and ask the user to choose.
- Support nearby-label resolution for form fields.
- Support OCR-based target resolution when UIA does not expose controls.
- Show the proposed target rectangle visually before approval.

### 4. Multi-Step Desktop Chains

- Allow the assistant to build chains such as open app, inspect screen, click target, type value, press hotkey.
- Require one approval for the whole chain after risk review.
- Stop the chain when observation changes unexpectedly.
- Add per-step verification after each action.
- Add rollback guidance where rollback is possible.

### 5. Browser Automation

- Add Playwright for browser-specific actions.
- Prefer DOM-level actions over screen-coordinate clicking inside browsers.
- Support tab inspection, page text extraction, form filling, and downloads.
- Keep browser actions behind the same plan-preview-confirm flow.

### 6. App and Window Control

- Add controlled window focus, minimize, maximize, close, and switch actions.
- Add app launch by known app names, not only paths.
- Add process/window inventory.
- Require confirmation for window-closing and app state changes.

### 7. Memory and Preferences

- Store user preferences locally.
- Remember trusted folders and commonly used apps.
- Add opt-in task history summaries.
- Keep sensitive data out of logs or redact it before saving.

### 8. Permissions and Policy Layer

- Add a local policy file for allowed and blocked tools.
- Add allowlists for folders, apps, and domains.
- Add stricter policies for messaging, deletion, payments, and settings changes.
- Add a "dry run only" mode.

### 9. Packaging

- Add a proper Windows launcher.
- Add `.env` support for local configuration.
- Add startup checks for optional dependencies.
- Package with a tray icon or desktop shortcut.
- Add logs and diagnostics view.

### 10. End-To-End Evaluation

- Add scripted tests for planner behavior.
- Add mocked UIA trees for target-resolution tests.
- Add local integration tests for file operations.
- Add manual acceptance scenarios for common desktop workflows.
- Track risk score changes with regression tests.

## Practical Next Milestone

The next best milestone is:

```text
Local LLM structured planner + richer UI target selection
```

That would move the assistant from deterministic command matching toward flexible English instructions while keeping the existing safety boundary: observe, plan, risk-score, preview, confirm, execute, verify.
