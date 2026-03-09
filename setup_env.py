#!/usr/bin/env python3
"""
Interactive setup: authenticates Claude CLI (OAuth) and Google Drive (rclone),
then writes all credentials to a .env file for local use or Coolify deployment.

Usage:
    python setup_env.py
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


CLAUDE_CREDENTIALS_PATH = Path.home() / '.claude' / '.credentials.json'


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
    print(f"{name} found")


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


def get_claude_credentials():
    """Read Claude OAuth credentials from ~/.claude/.credentials.json."""
    if not CLAUDE_CREDENTIALS_PATH.exists():
        return None
    try:
        data = json.loads(CLAUDE_CREDENTIALS_PATH.read_text())
        oauth = data.get('claudeAiOauth', {})
        if oauth.get('accessToken') and oauth.get('refreshToken'):
            return json.dumps(data)
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def verify_remote(remote, env_vars):
    merged = {**os.environ, **env_vars}
    result = subprocess.run(
        ['rclone', 'lsjson', remote, '--max-depth', '0'],
        capture_output=True, text=True, env=merged,
    )
    return result.returncode == 0


def write_env(values: dict, path: str = '.env'):
    lines = []
    for key, value in values.items():
        escaped = value.replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    print("Post Editor — Setup")
    print()
    print("This script will:")
    print("  1. Authenticate Claude CLI via OAuth (Max/Pro plan)")
    print("  2. Authenticate Google Drive via rclone")
    print("  3. Write everything to .env")

    # ── Dependencies
    banner("Checking dependencies")
    check_dependency('claude', 'Claude CLI', 'npm install -g @anthropic-ai/claude-code')
    check_dependency('rclone', 'rclone', 'https://rclone.org/install/')

    # ── Step 1: Claude CLI OAuth
    banner("Step 1 of 2 — Claude CLI authentication")

    creds = get_claude_credentials()
    if creds:
        print("Existing Claude credentials found.")
        result = subprocess.run(
            ['claude', 'auth', 'status'],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            try:
                status = json.loads(result.stdout)
                print(f"  Logged in as: {status.get('email', 'unknown')}")
                print(f"  Plan: {status.get('subscriptionType', 'unknown')}")
            except json.JSONDecodeError:
                print(f"  Status: {result.stdout.strip()}")

        reuse = ask("Use existing credentials? (y/n)", default="y")
        if reuse.lower() != 'y':
            creds = None

    if not creds:
        print("Opening browser for Claude OAuth login...")
        print("Sign in with your Anthropic account (Max/Pro plan required).")
        input("\nPress Enter to open the browser...")

        result = subprocess.run(['claude', 'auth', 'login'])
        if result.returncode != 0:
            print("ERROR: Claude login failed.")
            sys.exit(1)

        creds = get_claude_credentials()
        if not creds:
            print("ERROR: Could not read Claude credentials after login.")
            print(f"Expected at: {CLAUDE_CREDENTIALS_PATH}")
            sys.exit(1)

    print("Claude credentials captured")

    # ── Step 2: Google Drive
    banner("Step 2 of 2 — Google Drive authentication")

    gdrive_folder = ask(
        "Google Drive folder path",
        default="HIdrivenAI/hidrivenai_obsidian",
    )
    poll_interval = ask("Poll interval in seconds", default="300")

    print("\nYour browser will open to authenticate with Google.")
    print("Sign in and authorize rclone when prompted.")
    input("\nPress Enter to open the browser...")

    gd_token = authorize_and_get_token('drive')
    if not gd_token:
        print("ERROR: Could not capture Google Drive token from rclone output.")
        print("Try running 'rclone authorize drive' manually and copy the token.")
        sys.exit(1)
    print("Google Drive token captured")

    # ── Build .env
    banner("Writing .env")

    env = {
        'CLAUDE_CREDENTIALS_JSON': creds,
        'GDRIVE_REMOTE': f'gdrive:{gdrive_folder}',
        'POLL_INTERVAL_SECONDS': poll_interval,
        'RCLONE_CONFIG_GDRIVE_TYPE': 'drive',
        'RCLONE_CONFIG_GDRIVE_SCOPE': 'drive',
        'RCLONE_CONFIG_GDRIVE_TOKEN': gd_token,
    }

    write_env(env)
    print(".env written")

    # ── Verify GDrive
    banner("Verifying connections")
    rclone_env = {
        'RCLONE_CONFIG_GDRIVE_TYPE': 'drive',
        'RCLONE_CONFIG_GDRIVE_SCOPE': 'drive',
        'RCLONE_CONFIG_GDRIVE_TOKEN': gd_token,
    }
    remote = f'gdrive:{gdrive_folder}'
    if verify_remote(remote, rclone_env):
        print(f"Google Drive — connected to {remote}")
    else:
        print(f"Google Drive — could not list {remote} (folder may not exist yet)")

    # ── Next steps
    print()
    print("All done! Next steps:")
    print()
    print("  Run locally:")
    print("    python main.py")
    print()
    print("  Deploy to Coolify:")
    print("    Copy each line from .env into Coolify > Environment Variables.")
    print("    CLAUDE_CREDENTIALS_JSON and RCLONE_CONFIG_* vars replace local config files.")
    print()
    print("  .env contains OAuth tokens — keep it secret, never commit it.")


if __name__ == '__main__':
    main()
