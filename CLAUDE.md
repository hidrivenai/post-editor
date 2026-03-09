# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Python polling daemon that generates blog posts from an Obsidian vault's Kanban board. It reads the vault from Google Drive via rclone, uses the Claude CLI to select writing frameworks/styles and generate content, then writes the post back to the vault and advances the Kanban card to Review. Deployable to Coolify via Dockerfile.

## Running

```bash
# First-time setup (interactive OAuth):
python setup_env.py

# Run locally:
python main.py

# Run tests:
pytest

# Docker:
docker build -t post-editor .
docker run --env-file .env post-editor
```

Requires: Python 3.11+, rclone, Node.js (for Claude CLI). Dependencies in `requirements.txt`.

## Architecture

### Pipeline Flow (`main.py:run_once`)

1. Build vault index via rclone → download Kanban board → get WIP items
2. For each WIP item: download post card → gather context (notes, links) → sync vault subset locally for Claude → select framework → select style → generate post → upload to GDrive → update card → move to Review

### Key Files

- **`main.py`** — Polling daemon entry point. `run_once()` handles one poll cycle, `main()` loops with sleep.
- **`config.py`** — Loads env vars from `.env` via python-dotenv. Required: `ANTHROPIC_API_KEY`, `GDRIVE_REMOTE`. Optional: `POLL_INTERVAL_SECONDS` (default 300).
- **`rclone_ops.py`** — rclone CLI wrappers: `list_files`, `list_files_recursive`, `download_file`, `upload_file`. Handles Coolify quote escaping.
- **`vault_io.py`** — Vault-level operations: `build_vault_index`, `download_text`, `upload_text`, `resolve_wikilink`, `sync_for_claude`.
- **`kanban.py`** — Parses Obsidian Kanban plugin markdown format. Pure string I/O (no file operations).
- **`obsidian.py`** — Post card parsing. Pure string I/O: `read_post_card`, `extract_wikilinks`, `update_post_card_section`.
- **`pipeline.py`** — Per-item orchestration: prompt extraction, Claude CLI calls (`select_framework`, `select_style`, `generate_blog_post`), and `process_item` which ties it all together.
- **`setup_env.py`** — Interactive GDrive OAuth setup, writes `.env`.

### External Integration

- **Google Drive via rclone** — All vault files accessed through `rclone_ops.py`. Config via `RCLONE_CONFIG_GDRIVE_*` env vars (no rclone.conf needed).
- **Claude CLI** — Shells out to `claude -p` with `--add-dir <temp_dir>` for framework selection, style selection, and blog post generation. The temp dir contains only the vault files Claude needs, synced by `vault_io.sync_for_claude()`.

### Vault Layout Assumptions

The Obsidian vault on Google Drive (path set by `GDRIVE_REMOTE`) contains:
- `projects/Post Kanban.md` — Kanban board file
- `writing_frameworks/` — Framework guide `.md` files
- `styles/` — Style guide `.md` files
- Post cards are markdown files with H1 sections: `# Agent`, `# Relevant notes`, `# Relevant links`, `# Post`, `# Reviews`
- Generated posts are written to the vault root

### Post Card Format

Post cards use H1 headers as section delimiters. The `Agent` section contains freeform instructions (may include `framework:` / `style:` / `tone:` directives parsed by regex). `Relevant notes` and `Relevant links` are bullet lists of wikilinks or URLs.

### Deployment

Dockerfile installs Python 3.11, rclone, Node.js + Claude CLI. Configure via env vars matching `.env.example`. Deploy to Coolify by pointing at this repo and setting env vars.
