import os
from dotenv import load_dotenv

REQUIRED = ['GDRIVE_REMOTE']


def _env(key: str, default: str | None = None) -> str | None:
    """Get env var, stripping surrounding quotes if present."""
    val = os.environ.get(key, default)
    if val and len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
        val = val[1:-1]
    return val


def load_config() -> dict:
    load_dotenv()
    for key in REQUIRED:
        if not _env(key):
            raise ValueError(f"Missing required environment variable: {key}")
    return {
        'gdrive_remote': _env('GDRIVE_REMOTE'),
        'poll_interval': int(_env('POLL_INTERVAL_SECONDS', '300')),
    }
