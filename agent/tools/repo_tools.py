import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import REPO_ROOT


def read_repo_file(path: str) -> dict:
    """Read any file from the local repo by relative path."""
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return {"error": f"File not found: {path}"}
    try:
        content = full_path.read_text()
        return {"path": path, "content": content}
    except Exception as e:
        return {"error": str(e)}


def list_repo_files(directory: str = "contentops") -> dict:
    """List files under a repo directory."""
    full_path = REPO_ROOT / directory
    if not full_path.exists():
        return {"error": f"Directory not found: {directory}"}
    files = [
        str(p.relative_to(REPO_ROOT))
        for p in full_path.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    ]
    return {"directory": directory, "files": sorted(files)}
