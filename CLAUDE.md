# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Python CLI pipeline that generates blog posts from an Obsidian vault's Kanban board. It reads "post cards" (structured markdown notes) from WIP, uses the Claude CLI to select writing frameworks/styles and generate content, then writes the post back to the vault and advances the Kanban card to Review.

## Running

```bash
uv run ./writer.py
```

No dependencies beyond Python 3.8+ standard library. The `uv` runner handles execution via PEP 723 inline script metadata. There is no test suite, linter, or build step.

## Architecture

### Pipeline Flow (`writer.py:main`)

1. Parse Kanban board → get WIP items
2. For each WIP item: read its post card → gather context (notes, links) → select framework → select style → generate post → write file → update card → move to Review

### Key Files

- **`writer.py`** — Pipeline orchestrator. Contains `build_context()`, `select_framework()`, `select_style()`, `generate_blog_post()`, and prompt extraction helpers.
- **`utils/kanban.py`** — Parses Obsidian Kanban plugin markdown format (H2 sections with `- [ ]` checkbox items). Handles moving items between sections.
- **`utils/obsidian.py`** — Vault operations: resolve `[[wikilinks]]` to file paths, read/parse post cards (H1 section-based structure), create blog post files, update post card sections.

### External Integration

The tool shells out to `claude -p` (Claude CLI) with `--add-dir hidrivenai_obsidian` for three operations: framework selection, style selection, and blog post generation. Fallback defaults: `"narrative"` framework, `"casual"` style.

### Vault Layout Assumptions

The Obsidian vault is expected at `../hidrivenai_obsidian/` (sibling directory) with:
- `projects/Post Kanban.md` — Kanban board file
- `writing_frameworks/` — Framework guide `.md` files
- `styles/` — Style guide `.md` files
- Post cards are markdown files with H1 sections: `# Agent`, `# Relevant notes`, `# Relevant links`, `# Post`, `# Reviews`
- Generated posts are written to the vault root

### Post Card Format

Post cards use H1 headers as section delimiters. The `Agent` section contains freeform instructions (may include `framework:` / `style:` / `tone:` directives parsed by regex). `Relevant notes` and `Relevant links` are bullet lists of wikilinks or URLs.
