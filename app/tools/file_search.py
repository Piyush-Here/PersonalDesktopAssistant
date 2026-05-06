from __future__ import annotations

from pathlib import Path

from app.models.schemas import ExecutionResult


class FileSearchTool:
    def __init__(self) -> None:
        self.search_roots = [
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
        ]

    def preview(self, query: str) -> ExecutionResult:
        query_lower = query.lower()
        matches: list[Path] = []
        for root in self.search_roots:
            if not root.exists():
                continue
            try:
                for path in root.rglob("*"):
                    if path.is_file() and query_lower in path.name.lower():
                        matches.append(path)
                    if len(matches) >= 5:
                        break
            except PermissionError:
                continue
            if len(matches) >= 5:
                break

        if not matches:
            return ExecutionResult(
                success=True,
                message=f"No matching files found for '{query}'.",
                details=[f"Searched: {root}" for root in self.search_roots if root.exists()],
            )

        return ExecutionResult(
            success=True,
            message=f"Found {len(matches)} candidate file(s) for '{query}'.",
            details=[str(path) for path in matches],
        )
