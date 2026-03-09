import json
import logging
import os
import subprocess

log = logging.getLogger(__name__)

_env_cache: dict | None = None


def _strip_quotes(val: str) -> str:
    """Strip surrounding quotes and unescape backslash-escaped quotes.

    Handles single and double escaping (Coolify/Docker can add extra layers).
    """
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
        val = val[1:-1]
    # Unescape repeatedly until stable (handles double-escaping)
    prev = None
    while prev != val and '\\' in val:
        prev = val
        val = val.replace('\\\\', '\\').replace('\\"', '"')
    return val


def _clean_rclone_env() -> dict:
    """Build env dict with RCLONE_CONFIG_* values cleaned for rclone.

    Handles surrounding quotes and escaped quotes that Coolify/Docker
    can introduce when injecting JSON tokens as env vars.
    """
    global _env_cache
    if _env_cache is not None:
        return _env_cache

    env = os.environ.copy()
    for key, val in env.items():
        if key.startswith('RCLONE_CONFIG_'):
            env[key] = _strip_quotes(val)

    _env_cache = env
    return env


def reset_env_cache() -> None:
    """Reset the cached environment (useful for testing)."""
    global _env_cache
    _env_cache = None


def list_files(remote: str) -> list[dict]:
    """List files in remote, return list of {name, mod_time} dicts."""
    result = subprocess.run(
        ['rclone', 'lsjson', remote],
        capture_output=True, text=True, env=_clean_rclone_env()
    )
    if result.returncode != 0:
        raise RuntimeError(f"rclone lsjson failed: {result.stderr}")
    entries = json.loads(result.stdout or '[]')
    return [
        {'name': e['Name'], 'mod_time': e['ModTime']}
        for e in entries
        if not e.get('IsDir', False)
    ]


def list_files_recursive(remote: str) -> list[dict]:
    """List all files recursively in remote.

    Returns list of {name, path, mod_time} dicts where path is the
    relative path within the remote (e.g. 'subfolder/file.md').
    """
    result = subprocess.run(
        ['rclone', 'lsjson', '--recursive', remote],
        capture_output=True, text=True, env=_clean_rclone_env()
    )
    if result.returncode != 0:
        raise RuntimeError(f"rclone lsjson --recursive failed: {result.stderr}")
    entries = json.loads(result.stdout or '[]')
    return [
        {'name': e['Name'], 'path': e['Path'], 'mod_time': e['ModTime']}
        for e in entries
        if not e.get('IsDir', False)
    ]


def download_file(remote: str, filename: str, local_path: str) -> None:
    """Download a single file from remote to local_path."""
    result = subprocess.run(
        ['rclone', 'copyto', f'{remote}/{filename}', local_path],
        capture_output=True, text=True, env=_clean_rclone_env()
    )
    if result.returncode != 0:
        raise RuntimeError(f"rclone download failed for '{filename}': {result.stderr}")


def upload_file(local_path: str, remote: str, remote_filename: str) -> None:
    """Upload local_path to remote/remote_filename."""
    result = subprocess.run(
        ['rclone', 'copyto', local_path, f'{remote}/{remote_filename}'],
        capture_output=True, text=True, env=_clean_rclone_env()
    )
    if result.returncode != 0:
        raise RuntimeError(f"rclone upload failed for '{remote_filename}': {result.stderr}")
