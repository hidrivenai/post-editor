"""Kanban board parser and updater for Obsidian kanban plugin format.

All functions take/return strings — no file I/O.
"""

import re


def parse_kanban(content: str) -> dict[str, list[str]]:
    """Parse Kanban board content and return dict of sections with their items.

    Returns dict mapping section names to lists of item wikilinks/names.
    Example: {'Ideas': ['Can AI Replace...'], 'WIP': [...]}
    """
    sections = {}
    section_pattern = r'^## (.+)$'
    lines = content.split('\n')

    current_section = None
    section_items = []

    for line in lines:
        match = re.match(section_pattern, line)
        if match:
            if current_section:
                sections[current_section] = section_items
            current_section = match.group(1)
            section_items = []
        elif current_section and line.strip().startswith('- [ ]'):
            item = _extract_item_name(line)
            if item:
                section_items.append(item)
        elif line.strip().startswith('%% kanban:settings'):
            break

    if current_section:
        sections[current_section] = section_items

    return sections


def get_items_by_status(kanban_dict: dict[str, list[str]], status: str) -> list[str]:
    """Get list of items in a given section."""
    return kanban_dict.get(status, [])


def move_item(content: str, item_name: str, from_section: str, to_section: str) -> str:
    """Move an item from one section to another. Returns modified content string."""
    lines = content.split('\n')

    # Find and remove item from source section
    item_line = None
    new_lines = []
    in_from_section = False

    for line in lines:
        if line.startswith('## '):
            section_name = line[3:].strip()
            in_from_section = (section_name == from_section)
            new_lines.append(line)
        elif in_from_section and _extract_item_name(line) == item_name:
            item_line = line
        else:
            new_lines.append(line)

    if not item_line:
        raise ValueError(f"Item '{item_name}' not found in section '{from_section}'")

    # Add item to target section
    final_lines = []
    in_to_section = False
    to_section_found = False
    item_added = False

    for line in new_lines:
        final_lines.append(line)

        if line.startswith('## '):
            section_name = line[3:].strip()
            if section_name == to_section:
                in_to_section = True
                to_section_found = True
            elif in_to_section and not item_added:
                final_lines.pop()
                final_lines.append(item_line)
                final_lines.append('')
                final_lines.append(line)
                item_added = True
                in_to_section = False

        elif in_to_section and line.strip().startswith('%% kanban:settings'):
            final_lines.pop()
            final_lines.append(item_line)
            final_lines.append('')
            final_lines.append(line)
            item_added = True
            in_to_section = False

    if to_section_found and not item_added:
        settings_index = None
        for i, line in enumerate(final_lines):
            if line.strip().startswith('%% kanban:settings'):
                settings_index = i
                break

        if settings_index:
            final_lines.insert(settings_index, item_line)
            final_lines.insert(settings_index + 1, '')
        else:
            final_lines.append(item_line)
            final_lines.append('')

    return '\n'.join(final_lines)


def _extract_item_name(line: str) -> str:
    """Extract item name from a checkbox line."""
    line = line.strip()
    if not line.startswith('- [ ]'):
        return ''

    content = line[5:].strip()

    wikilink_match = re.match(r'\[\[([^\]]+)\]\]', content)
    if wikilink_match:
        return wikilink_match.group(1)

    return content
