import pytest
from tools import source_backends as sb
from tools.source_backends import LocalFsSource, get_source, resolve_source_name


@pytest.fixture
def local_source(tmp_path):
    (tmp_path / "founder-notes.md").write_text("# Notes\nproduction reliability matters", encoding="utf-8")
    (tmp_path / "blog-q1.txt").write_text("a blog about workflow ownership", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "transcript.md").write_text("call transcript", encoding="utf-8")
    return LocalFsSource(root=str(tmp_path)), tmp_path


def test_localfs_lists_and_filters(local_source):
    src, _ = local_source
    names = {f["name"] for f in src.list()["files"]}
    assert {"founder-notes.md", "blog-q1.txt", "transcript.md"} <= names

    filtered = src.list(query="blog")
    assert [f["name"] for f in filtered["files"]] == ["blog-q1.txt"]


def test_localfs_reads_by_relative_path(local_source):
    src, _ = local_source
    doc = src.read("founder-notes.md")
    assert "reliability" in doc["content"]
    assert doc["name"] == "founder-notes.md"

    nested = src.read("sub/transcript.md")
    assert nested["content"] == "call transcript"


def test_localfs_missing_file_errors(local_source):
    src, _ = local_source
    assert "error" in src.read("nope.md")


def test_localfs_blocks_path_traversal(local_source):
    src, _ = local_source
    res = src.read("../../etc/passwd")
    assert "error" in res  # escapes the source dir → refused


def test_source_resolution_prefers_explicit_then_legacy(monkeypatch):
    monkeypatch.setattr(sb, "SOURCE_BACKEND", "localfs")
    assert resolve_source_name() == "localfs"
    assert isinstance(get_source(), LocalFsSource)

    monkeypatch.setattr(sb, "SOURCE_BACKEND", "")
    monkeypatch.setattr(sb, "GOOGLE_AUTH_MODE", "apps_script")
    assert resolve_source_name() == "apps_script"

    monkeypatch.setattr(sb, "GOOGLE_AUTH_MODE", "service_account")
    assert resolve_source_name() == "gdrive"


def test_unknown_source_raises(monkeypatch):
    monkeypatch.setattr(sb, "SOURCE_BACKEND", "weird")
    with pytest.raises(ValueError):
        get_source()
