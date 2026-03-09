"""Vault file operations via rclone — bridges rclone_ops with vault-specific needs."""

import logging
import os
import tempfile
from pathlib import Path

from rclone_ops import list_files_recursive, download_file, upload_file

log = logging.getLogger(__name__)


def build_vault_index(cfg: dict) -> dict:
    """Build {stem: relative_path} lookup for all .md files in the vault.

    Called once per poll cycle so wikilinks can be resolved without
    repeated rclone calls.
    """
    entries = list_files_recursive(cfg['gdrive_remote'])
    index = {}
    for e in entries:
        if e['path'].endswith('.md'):
            stem = Path(e['path']).stem
            index[stem] = e['path']
    return index


def download_text(cfg: dict, rel_path: str) -> str:
    """Download a text file from the vault and return its content."""
    fd, tmp_path = tempfile.mkstemp(suffix='.md')
    os.close(fd)
    try:
        download_file(cfg['gdrive_remote'], rel_path, tmp_path)
        with open(tmp_path, 'r', encoding='utf-8') as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def upload_text(cfg: dict, rel_path: str, content: str) -> None:
    """Write content to a temp file and upload it to the vault."""
    fd, tmp_path = tempfile.mkstemp(suffix='.md')
    os.close(fd)
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        upload_file(tmp_path, cfg['gdrive_remote'], rel_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def resolve_wikilink(vault_index: dict, name: str) -> str | None:
    """Look up a wikilink name in the vault index, return relative path or None."""
    return vault_index.get(name)


def sync_for_claude(cfg: dict, vault_index: dict, needed_dirs: list[str],
                    needed_notes: list[str]) -> Path:
    """Download relevant vault files to a temp directory for claude -p --add-dir.

    Downloads:
    - All .md files from each directory in needed_dirs (e.g. 'writing_frameworks', 'styles')
    - Specific note files listed in needed_notes (relative paths)

    Returns the temp directory path. Caller is responsible for cleanup.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix='post_editor_vault_'))
    vault_name = 'hidrivenai_obsidian'
    vault_dir = tmp_dir / vault_name

    # Download directory contents
    for dir_name in needed_dirs:
        dir_prefix = dir_name.rstrip('/') + '/'
        for stem, rel_path in vault_index.items():
            if rel_path.startswith(dir_prefix) and rel_path.endswith('.md'):
                local_path = vault_dir / rel_path
                local_path.parent.mkdir(parents=True, exist_ok=True)
                download_file(cfg['gdrive_remote'], rel_path, str(local_path))

    # Download specific notes
    for rel_path in needed_notes:
        local_path = vault_dir / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        download_file(cfg['gdrive_remote'], rel_path, str(local_path))

    return tmp_dir
