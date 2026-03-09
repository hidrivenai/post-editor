import json
import logging
import os
import time
from pathlib import Path

import kanban
import pipeline
import vault_io
from config import load_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


def setup_claude_credentials() -> None:
    """Write Claude OAuth credentials from env var to ~/.claude/.credentials.json.

    Needed for Docker/Coolify where the credentials file doesn't exist.
    Skipped if the file already exists (local dev) or env var is not set.
    """
    creds_path = Path.home() / '.claude' / '.credentials.json'
    if creds_path.exists():
        return

    creds_json = os.environ.get('CLAUDE_CREDENTIALS_JSON', '')
    if not creds_json:
        log.warning("No CLAUDE_CREDENTIALS_JSON env var and no credentials file. "
                     "Claude CLI may not be authenticated.")
        return

    # Validate it's proper JSON
    try:
        json.loads(creds_json)
    except json.JSONDecodeError:
        log.error("CLAUDE_CREDENTIALS_JSON is not valid JSON")
        return

    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(creds_json)
    creds_path.chmod(0o600)
    log.info("Claude credentials written from env var")


def run_once(cfg: dict) -> None:
    """One poll cycle: index vault, find WIP items, process each."""
    vault_index = vault_io.build_vault_index(cfg)
    kanban_content = vault_io.download_text(cfg, "projects/Post Kanban.md")
    wip_items = kanban.get_items_by_status(
        kanban.parse_kanban(kanban_content), "WIP"
    )

    if not wip_items:
        log.info("No WIP items.")
        return

    log.info(f"Found {len(wip_items)} WIP item(s)")
    for item in wip_items:
        try:
            pipeline.process_item(item, cfg, vault_index)
        except Exception as e:
            log.error(f"Failed to process {item}: {e}")


def main() -> None:
    setup_claude_credentials()
    cfg = load_config()
    log.info(f'Starting. Poll interval: {cfg["poll_interval"]}s')
    while True:
        try:
            run_once(cfg)
        except Exception as e:
            log.error(f"Poll cycle error: {e}")
        time.sleep(cfg['poll_interval'])


if __name__ == '__main__':
    main()
