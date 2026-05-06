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

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Notes

- The current V1 is deterministic and local-first. It does not depend on an LLM yet.
- `app_open` can execute after confirmation when the target path exists.
- File move, rename, copy, delete, OCR, and deep UI automation are intentionally staged and not fully enabled yet.

## Next engineering steps

- Add real Windows UI Automation and OCR adapters
- Add Playwright browser automation
- Add a tool-calling LLM layer for stronger intent extraction
- Add richer file-operation argument parsing with explicit previews
