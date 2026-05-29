"""Knowledge-source facade.

Stable, agent-facing API for reading source material. Delegates to whichever
`SourceBackend` is configured (Google Drive, Apps Script, local folder, …) so
the agent tools never depend on a specific platform. Backends live in
tools/source_backends.py; select with SOURCE_BACKEND.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.source_backends import get_source


def read_drive_doc(doc_id: str) -> dict:
    """Read a document's text content by ID, path, or URL."""
    return get_source().read(doc_id)


def list_drive_files(query: str = "") -> dict:
    """List available source documents, optionally filtered by name."""
    return get_source().list(query)
