"""Obsidian vault utilities for working with markdown files and wikilinks."""

import re
from pathlib import Path
from typing import List, Dict, Optional


def read_note(vault_path: Path, note_name: str) -> str:
    """
    Read a markdown file by wikilink name.

    Args:
        vault_path: Path to the Obsidian vault
        note_name: Name of the note (without .md extension)

    Returns:
        Content of the note file

    Raises:
        FileNotFoundError: If note doesn't exist
    """
    file_path = resolve_wikilink(vault_path, note_name)
    if not file_path:
        raise FileNotFoundError(f"Note not found: {note_name}")

    return file_path.read_text(encoding='utf-8')


def extract_wikilinks(content: str) -> List[str]:
    """
    Extract all [[...]] wikilinks from text.

    Args:
        content: Markdown content to parse

    Returns:
        List of wikilink names (without brackets)
    """
    pattern = r'\[\[([^\]]+)\]\]'
    matches = re.findall(pattern, content)
    return matches


def resolve_wikilink(vault_path: Path, wikilink: str) -> Optional[Path]:
    """
    Find actual file path for a wikilink.
    Searches vault root and subdirectories.

    Args:
        vault_path: Path to the Obsidian vault
        wikilink: Name of the note (may include path separators)

    Returns:
        Path to the file, or None if not found
    """
    # Try exact match in root
    direct_path = vault_path / f"{wikilink}.md"
    if direct_path.exists():
        return direct_path

    # Search in subdirectories
    for md_file in vault_path.rglob("*.md"):
        if md_file.stem == wikilink:
            return md_file

    return None


def read_post_card(file_path: Path) -> Dict[str, any]:
    """
    Parse post card structure into dict with sections.

    Post card sections (H1 headers):
    - # Agent
    - # Relevant notes
    - # Relevant links
    - # Post
    - # Reviews

    Args:
        file_path: Path to post card markdown file

    Returns:
        Dict with keys: 'Agent', 'Relevant notes', 'Relevant links', 'Post', 'Reviews'
        Each value contains the content under that section
    """
    content = file_path.read_text(encoding='utf-8')

    sections = {
        'Agent': '',
        'Relevant notes': [],
        'Relevant links': [],
        'Post': '',
        'Reviews': []
    }

    # Split by H1 headers
    section_pattern = r'^# (.+)$'
    lines = content.split('\n')

    current_section = None
    section_content = []

    for line in lines:
        match = re.match(section_pattern, line)
        if match:
            # Save previous section
            if current_section:
                sections[current_section] = _parse_section_content(
                    current_section, '\n'.join(section_content)
                )

            # Start new section
            current_section = match.group(1)
            section_content = []
        elif current_section:
            section_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = _parse_section_content(
            current_section, '\n'.join(section_content)
        )

    return sections


def _parse_section_content(section_name: str, content: str) -> any:
    """Parse section content based on section type."""
    content = content.strip()

    if section_name in ['Relevant notes', 'Relevant links', 'Reviews']:
        # Parse as list - extract items from bullet points or lines
        items = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('-'):
                # Remove bullet and whitespace
                item = line.lstrip('- ').strip()
                if item:
                    # For wikilinks, extract just the name
                    if item.startswith('[[') and item.endswith(']]'):
                        item = item[2:-2]
                    # For markdown links [text](url), extract the URL
                    elif '[' in item and '](' in item:
                        match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', item)
                        if match:
                            item = match.group(2)  # Extract URL/path
                    items.append(item)
            elif line and not line.startswith('#'):
                # Plain line (like URLs)
                items.append(line)
        return items
    else:
        # Return as string (Agent, Post sections)
        return content


def update_post_card_section(file_path: Path, section_name: str, content: str):
    """
    Update a specific section in a post card file.

    Args:
        file_path: Path to post card file
        section_name: Name of the section to update (e.g., 'Post')
        content: New content for the section
    """
    original_content = file_path.read_text(encoding='utf-8')
    lines = original_content.split('\n')

    # Find section and update
    section_pattern = f'^# {re.escape(section_name)}$'
    new_lines = []
    in_target_section = False
    section_found = False

    i = 0
    while i < len(lines):
        line = lines[i]

        if re.match(section_pattern, line):
            # Found target section
            section_found = True
            in_target_section = True
            new_lines.append(line)
            new_lines.append(content)
            i += 1

            # Skip old content until next section or end
            while i < len(lines) and not lines[i].startswith('# '):
                i += 1
            continue

        new_lines.append(line)
        i += 1

    if not section_found:
        # Section doesn't exist, add it at the end
        new_lines.append(f'\n# {section_name}')
        new_lines.append(content)

    file_path.write_text('\n'.join(new_lines), encoding='utf-8')


def create_blog_post(vault_path: Path, title: str, content: str) -> Path:
    """
    Create a new blog post markdown file.

    Args:
        vault_path: Path to Obsidian vault
        title: Title of the blog post (used as filename)
        content: Markdown content for the post

    Returns:
        Path to created file
    """
    # Sanitize filename
    safe_title = title.replace('/', '-').replace('\\', '-')
    file_path = vault_path / f"{safe_title}.md"

    # Ensure unique filename
    counter = 1
    while file_path.exists():
        file_path = vault_path / f"{safe_title} {counter}.md"
        counter += 1

    file_path.write_text(content, encoding='utf-8')
    return file_path
