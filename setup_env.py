#!/usr/bin/env python3
"""
Interactive setup for post-editor credentials.

Usage:
    python setup_env.py          # Set up everything
    python setup_env.py --claude  # Set up Claude auth only
    python setup_env.py --gdrive  # Set up Google Drive only
    python setup_env.py --config  # Set up poll interval and GDrive path only
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ENV_PATH = '.env'


def banner(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def ask(prompt, default=None):
    display = f"{prompt} [{default}]: " if default else f"{prompt}: "
    value = input(display).strip()
    return value if value else default


def check_dependency(cmd, name, install_hint):
    result = subprocess.run([cmd, '--version'], capture_output=True)
    if result.returncode != 0:
        print(f"ERROR: {name} is not installed.")
        print(f"Install: {install_hint}")
        sys.exit(1)
    print(f"  {name} found")


def read_env() -> dict:
    """Read existing .env file into a dict, preserving values."""
    env = {}
    if not os.path.exists(ENV_PATH):
        return env
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                # Strip surrounding quotes
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                env[key] = value
    return env


def write_env(values: dict):
    """Write dict to .env file. Merges with existing values."""
    existing = read_env()
    existing.update(values)
    lines = []
    for key, value in existing.items():
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')
    with open(ENV_PATH, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def authorize_and_get_token(rclone_type):
    """Run `rclone authorize <type>` — OAuth browser flow only."""
    result = subprocess.run(
        ['rclone', 'authorize', rclone_type],
        stdout=subprocess.PIPE, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: rclone authorize failed for '{rclone_type}'.")
        sys.exit(1)

    stdout = result.stdout
    match = re.search(
        r'Paste the following into your remote machine\s*--->\s*(.+?)\s*<---',
        stdout, re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    match = re.search(r'\{[^{}]*"access_token"[^{}]*\}', stdout)
    if match:
        return match.group(0).strip()

    return None


def verify_remote(remote, env_vars):
    merged = {**os.environ, **env_vars}
    result = subprocess.run(
        ['rclone', 'lsjson', remote, '--max-depth', '0'],
        capture_output=True, text=True, env=merged,
    )
    return result.returncode == 0


# ── Setup sections ───────────────────────────────────────────────


def setup_claude():
    """Set up Claude authentication (API key or OAuth token)."""
    banner("Claude authentication")

    print("Choose authentication method:\n")
    print("  1. API key  — from console.anthropic.com (recommended for servers)")
    print("  2. OAuth    — via 'claude setup-token' (uses Max/Pro plan credits)")
    print()
    choice = ask("Method (1 or 2)", default="1")

    env = {}

    if choice == "2":
        check_dependency('claude', 'Claude CLI', 'npm install -g @anthropic-ai/claude-code')
        print("\nThis will generate a long-lived OAuth token for headless use.")
        print("Follow the instructions from the Claude CLI.\n")

        result = subprocess.run(['claude', 'setup-token'], text=True)
        if result.returncode != 0:
            print("ERROR: claude setup-token failed.")
            sys.exit(1)

        # Read the credentials file that setup-token wrote
        creds_path = Path.home() / '.claude' / '.credentials.json'
        if not creds_path.exists():
            print(f"ERROR: Credentials file not found at {creds_path}")
            sys.exit(1)

        try:
            data = json.loads(creds_path.read_text())
            env['CLAUDE_CREDENTIALS_JSON'] = json.dumps(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"ERROR: Could not read credentials: {e}")
            sys.exit(1)

        # Remove API key if switching to OAuth
        existing = read_env()
        if 'ANTHROPIC_API_KEY' in existing:
            env['ANTHROPIC_API_KEY'] = ''
            print("(Cleared existing ANTHROPIC_API_KEY)")

        print("Claude OAuth token captured")

    else:
        api_key = ask("Anthropic API key (sk-ant-...)")
        if not api_key:
            print("ERROR: API key is required.")
            sys.exit(1)
        env['ANTHROPIC_API_KEY'] = api_key

        # Remove OAuth creds if switching to API key
        existing = read_env()
        if 'CLAUDE_CREDENTIALS_JSON' in existing:
            env['CLAUDE_CREDENTIALS_JSON'] = ''
            print("(Cleared existing CLAUDE_CREDENTIALS_JSON)")

        print("API key saved")

    write_env(env)
    print(f"Updated {ENV_PATH}")


def setup_gdrive():
    """Set up Google Drive authentication via rclone."""
    banner("Google Drive authentication")
    check_dependency('rclone', 'rclone', 'https://rclone.org/install/')

    gdrive_folder = ask(
        "Google Drive folder path",
        default=read_env().get('GDRIVE_REMOTE', '').replace('gdrive:', '') or "HIdrivenAI/hidrivenai_obsidian",
    )

    print("\nYour browser will open to authenticate with Google.")
    print("Sign in and authorize rclone when prompted.")
    input("\nPress Enter to open the browser...")

    gd_token = authorize_and_get_token('drive')
    if not gd_token:
        print("ERROR: Could not capture Google Drive token from rclone output.")
        print("Try running 'rclone authorize drive' manually and copy the token.")
        sys.exit(1)

    env = {
        'GDRIVE_REMOTE': f'gdrive:{gdrive_folder}',
        'RCLONE_CONFIG_GDRIVE_TYPE': 'drive',
        'RCLONE_CONFIG_GDRIVE_SCOPE': 'drive',
        'RCLONE_CONFIG_GDRIVE_TOKEN': gd_token,
    }

    write_env(env)
    print("Google Drive token captured")

    # Verify
    rclone_env = {k: v for k, v in env.items() if k.startswith('RCLONE_')}
    remote = env['GDRIVE_REMOTE']
    if verify_remote(remote, rclone_env):
        print(f"Verified — connected to {remote}")
    else:
        print(f"Warning — could not list {remote} (folder may not exist yet)")

    print(f"Updated {ENV_PATH}")


def setup_config():
    """Set up non-secret configuration (poll interval, GDrive path)."""
    banner("Configuration")

    existing = read_env()

    gdrive_folder = ask(
        "Google Drive folder path",
        default=existing.get('GDRIVE_REMOTE', '').replace('gdrive:', '') or "HIdrivenAI/hidrivenai_obsidian",
    )
    poll_interval = ask(
        "Poll interval in seconds",
        default=existing.get('POLL_INTERVAL_SECONDS', '300'),
    )

    env = {
        'GDRIVE_REMOTE': f'gdrive:{gdrive_folder}',
        'POLL_INTERVAL_SECONDS': poll_interval,
    }

    write_env(env)
    print(f"Updated {ENV_PATH}")


def setup_all():
    """Full setup — Claude + GDrive + config."""
    print("Post Editor — Full Setup")
    print()
    print("This will set up:")
    print("  1. Claude authentication (API key or OAuth)")
    print("  2. Google Drive authentication (rclone)")
    print("  3. Configuration (poll interval)")

    setup_claude()
    setup_gdrive()

    # Poll interval
    existing = read_env()
    poll_interval = ask(
        "Poll interval in seconds",
        default=existing.get('POLL_INTERVAL_SECONDS', '300'),
    )
    write_env({'POLL_INTERVAL_SECONDS': poll_interval})

    print()
    print("All done! Next steps:")
    print()
    print("  Run locally:    python main.py")
    print("  Deploy:         Copy .env values into Coolify environment variables")
    print()
    print("  .env contains secrets — never commit it.")


def main():
    parser = argparse.ArgumentParser(
        description="Set up post-editor credentials and configuration.",
        epilog="Run without flags for full setup.",
    )
    parser.add_argument('--claude', action='store_true', help='Set up Claude authentication only')
    parser.add_argument('--gdrive', action='store_true', help='Set up Google Drive authentication only')
    parser.add_argument('--config', action='store_true', help='Set up poll interval and GDrive path only')
    args = parser.parse_args()

    if not any([args.claude, args.gdrive, args.config]):
        setup_all()
    else:
        if args.claude:
            setup_claude()
        if args.gdrive:
            setup_gdrive()
        if args.config:
            setup_config()


if __name__ == '__main__':
    main()
