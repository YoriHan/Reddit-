# reddit_toolkit/extractor.py
import os

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}
_TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".json", ".yaml", ".yml",
                    ".ts", ".js", ".go", ".rb", ".env.example"}


def read_file(path: str, max_chars: int = 8000) -> str:
    """Read a single file and return its content, truncated to max_chars."""
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read(max_chars)
    return f"# {os.path.basename(path)}\n\n{content}"


def read_codebase(path: str, max_chars: int = 40000) -> str:
    """Walk a directory (depth <= 3) and concatenate text file contents up to max_chars."""
    parts = []
    total = 0
    root = os.path.abspath(path)

    for dirpath, dirnames, filenames in os.walk(root):
        # Depth check
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 3:
            dirnames.clear()
            continue

        # Skip hidden/build dirs in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]

        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _TEXT_EXTENSIONS:
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    chunk = f.read(max_chars - total)
                if not chunk:
                    break
                rel_path = os.path.relpath(fpath, root)
                parts.append(f"# {rel_path}\n\n{chunk}")
                total += len(chunk)
            except OSError:
                continue
            if total >= max_chars:
                break
        if total >= max_chars:
            break

    return "\n\n---\n\n".join(parts)
