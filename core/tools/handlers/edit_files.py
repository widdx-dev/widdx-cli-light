"""Edit files tool — atomic multi-file editing."""

from pathlib import Path


def _handle_edit_files(files: list[dict]) -> str:
    from core.multi_editor import MultiFileEditor
    editor = MultiFileEditor()
    try:
        from core.diff_engine import DiffEngine
        differ = DiffEngine()
    except Exception:
        differ = None

    results = []
    for i, edit in enumerate(files):
        path = Path(edit["path"])
        old_str = edit["old_string"]
        new_str = edit["new_string"]
        if not path.exists():
            results.append(f"[{i}] SKIP: {path} does not exist")
            continue
        current = path.read_text(encoding="utf-8")
        if old_str not in current:
            results.append(f"[{i}] SKIP: old_string not found in {path}")
            continue
        new_content = current.replace(old_str, new_str, 1)
        if differ:
            diff_preview = differ.generate(filename=path.name, old_text=current, new_text=new_content)[:300]
            results.append(f"[{i}] DIFF {path}:\n{diff_preview}")
        else:
            results.append(f"[{i}] EDIT {path}")
        editor.add(str(path), new_content)

    if editor.staged_count == 0:
        return "\n".join(results) if results else "No files to edit"
    r = editor.commit()
    if r.ok:
        results.append(f"\n✓ Atomic commit: {r.files_written} files written")
    else:
        results.append(f"\n✗ FAILED: {', '.join(r.errors)} (rolled back)")
    return "\n".join(results)
