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


def setup_claude_auth() -> None:
    """Ensure Claude CLI is authenticated and onboarding is skipped.

    Priority:
    1. ANTHROPIC_API_KEY env var — Claude CLI uses this automatically.
    2. CLAUDE_CODE_OAUTH_TOKEN env var — Claude CLI uses this automatically.
    3. CLAUDE_CREDENTIALS_JSON env var — write to ~/.claude/.credentials.json.
    4. Existing credentials file — local dev, nothing to do.

    Also ensures ~/.claude.json has hasCompletedOnboarding=true so the CLI
    doesn't prompt for theme/auth selection in Docker.
    """
    _ensure_onboarding_complete()

    if os.environ.get('ANTHROPIC_API_KEY'):
        log.info("Using ANTHROPIC_API_KEY for Claude authentication")
        return

    if os.environ.get('CLAUDE_CODE_OAUTH_TOKEN'):
        log.info("Using CLAUDE_CODE_OAUTH_TOKEN for Claude authentication")
        return

    creds_path = Path.home() / '.claude' / '.credentials.json'
    if creds_path.exists():
        log.info("Using existing Claude credentials file")
        return

    creds_json = os.environ.get('CLAUDE_CREDENTIALS_JSON', '')
    if not creds_json:
        log.warning("No ANTHROPIC_API_KEY, no CLAUDE_CODE_OAUTH_TOKEN, "
                     "no CLAUDE_CREDENTIALS_JSON, and no credentials file. "
                     "Claude CLI will not be authenticated.")
        return

    # Strip surrounding quotes that Coolify/Docker can add
    if len(creds_json) >= 2 and creds_json[0] == creds_json[-1] and creds_json[0] in ('"', "'"):
        creds_json = creds_json[1:-1]
    # Unescape backslash-escaped quotes (Coolify double-escaping)
    prev = None
    while prev != creds_json and '\\' in creds_json:
        prev = creds_json
        creds_json = creds_json.replace('\\\\', '\\').replace('\\"', '"')

    # Validate it's proper JSON
    try:
        json.loads(creds_json)
    except json.JSONDecodeError:
        log.error(f"CLAUDE_CREDENTIALS_JSON is not valid JSON after unescaping: {creds_json[:100]}...")
        return

    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(creds_json)
    creds_path.chmod(0o600)
    log.info("Claude OAuth credentials written from env var")


def _ensure_onboarding_complete() -> None:
    """Ensure ~/.claude.json has hasCompletedOnboarding=true.

    Without this, the Claude CLI prompts for theme/auth selection
    even when CLAUDE_CODE_OAUTH_TOKEN is set.
    """
    config_path = Path.home() / '.claude.json'
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            config = {}

    if config.get('hasCompletedOnboarding'):
        return

    config['hasCompletedOnboarding'] = True
    config_path.write_text(json.dumps(config))
    log.info("Set hasCompletedOnboarding in ~/.claude.json")


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
    setup_claude_auth()
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
