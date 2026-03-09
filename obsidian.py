"""Obsidian vault utilities — pure parsing, no file I/O."""

import re


def read_post_card(content: str) -> dict:
    """Parse post card content into dict with sections.

    Post card sections (H1 headers):
    - # Agent
    - # Relevant notes
    - # Relevant links
    - # Post
    - # Reviews

    Returns dict with section names as keys.
    """
    sections = {
        'Agent': '',
        'Relevant notes': [],
        'Relevant links': [],
        'Post': '',
        'Reviews': []
    }

    section_pattern = r'^# (.+)$'
    lines = content.split('\n')

    current_section = None
    section_content = []

    for line in lines:
        match = re.match(section_pattern, line)
        if match:
            if current_section:
                sections[current_section] = _parse_section_content(
                    current_section, '\n'.join(section_content)
                )
            current_section = match.group(1)
            section_content = []
        elif current_section:
            section_content.append(line)

    if current_section:
        sections[current_section] = _parse_section_content(
            current_section, '\n'.join(section_content)
        )

    return sections


def extract_wikilinks(content: str) -> list[str]:
    """Extract all [[...]] wikilinks from text."""
    pattern = r'\[\[([^\]]+)\]\]'
    return re.findall(pattern, content)


def update_post_card_section(content: str, section_name: str, new_content: str) -> str:
    """Update a specific section in a post card. Returns modified content string."""
    lines = content.split('\n')
    section_pattern = f'^# {re.escape(section_name)}$'
    new_lines = []
    section_found = False

    i = 0
    while i < len(lines):
        line = lines[i]

        if re.match(section_pattern, line):
            section_found = True
            new_lines.append(line)
            new_lines.append(new_content)
            i += 1
            # Skip old content until next section or end
            while i < len(lines) and not lines[i].startswith('# '):
                i += 1
            continue

        new_lines.append(line)
        i += 1

    if not section_found:
        new_lines.append(f'\n# {section_name}')
        new_lines.append(new_content)

    return '\n'.join(new_lines)


def _parse_section_content(section_name: str, content: str):
    """Parse section content based on section type."""
    content = content.strip()

    if section_name in ['Relevant notes', 'Relevant links', 'Reviews']:
        items = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('-'):
                item = line.lstrip('- ').strip()
                if item:
                    if item.startswith('[[') and item.endswith(']]'):
                        item = item[2:-2]
                    elif '[' in item and '](' in item:
                        match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', item)
                        if match:
                            item = match.group(2)
                    items.append(item)
            elif line and not line.startswith('#'):
                items.append(line)
        return items
    else:
        return content
