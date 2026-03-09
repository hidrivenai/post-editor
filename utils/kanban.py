"""Kanban board parser and updater for Obsidian kanban plugin format."""

import re
from pathlib import Path
from typing import Dict, List


def parse_kanban(file_path: Path) -> Dict[str, List[str]]:
    """
    Parse Kanban board and return dict of sections with their items.

    Args:
        file_path: Path to Kanban board markdown file

    Returns:
        Dict mapping section names to lists of item wikilinks/names
        Example: {'Ideas': ['Can AI Replace...', 'Universal Basic...'], 'WIP': [...]}
    """
    content = file_path.read_text(encoding='utf-8')
    sections = {}

    # Split by H2 headers (## Section Name)
    section_pattern = r'^## (.+)$'
    lines = content.split('\n')

    current_section = None
    section_items = []

    for line in lines:
        # Check for section header
        match = re.match(section_pattern, line)
        if match:
            # Save previous section
            if current_section:
                sections[current_section] = section_items

            # Start new section
            current_section = match.group(1)
            section_items = []

        # Check for item in current section
        elif current_section and line.strip().startswith('- [ ]'):
            # Extract item name
            item = _extract_item_name(line)
            if item:
                section_items.append(item)

        # Stop at kanban settings block
        elif line.strip().startswith('%% kanban:settings'):
            break

    # Save last section
    if current_section:
        sections[current_section] = section_items

    return sections


def get_items_by_status(kanban_dict: Dict[str, List[str]], status: str) -> List[str]:
    """
    Get list of items in a given section.

    Args:
        kanban_dict: Dict returned by parse_kanban()
        status: Section name (e.g., 'WIP', 'Review', 'Done')

    Returns:
        List of item names in that section
    """
    return kanban_dict.get(status, [])


def move_item(file_path: Path, item_name: str, from_section: str, to_section: str):
    """
    Move an item from one section to another in the Kanban board.
    Preserves YAML frontmatter and plugin settings.

    Args:
        file_path: Path to Kanban board file
        item_name: Name of the item to move (wikilink name without brackets)
        from_section: Source section name
        to_section: Target section name
    """
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Find and remove item from source section
    item_line = None
    new_lines = []
    in_from_section = False
    from_section_found = False

    for i, line in enumerate(lines):
        # Check for section headers
        if line.startswith('## '):
            section_name = line[3:].strip()
            in_from_section = (section_name == from_section)
            if in_from_section:
                from_section_found = True
            new_lines.append(line)

        # Check if this is the item to move
        elif in_from_section and _extract_item_name(line) == item_name:
            item_line = line
            # Don't add to new_lines (remove it)

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

        # Check for target section header
        if line.startswith('## '):
            section_name = line[3:].strip()

            # If we just entered the target section, prepare to add item
            if section_name == to_section:
                in_to_section = True
                to_section_found = True

            # If we were in target section and hit a new section, add item before this section
            elif in_to_section and not item_added:
                # Insert before the new section header (remove it first)
                final_lines.pop()
                final_lines.append(item_line)
                final_lines.append('')
                final_lines.append(line)  # Re-add the section header
                item_added = True
                in_to_section = False

        # If we're in target section and hit the settings block, add item before it
        elif in_to_section and line.strip().startswith('%% kanban:settings'):
            final_lines.pop()  # Remove settings line
            final_lines.append(item_line)
            final_lines.append('')
            final_lines.append(line)  # Re-add settings line
            item_added = True
            in_to_section = False

    # If item wasn't added yet and we found the target section, add at end before settings
    if to_section_found and not item_added:
        # Find settings block and insert before it
        settings_index = None
        for i, line in enumerate(final_lines):
            if line.strip().startswith('%% kanban:settings'):
                settings_index = i
                break

        if settings_index:
            final_lines.insert(settings_index, item_line)
            final_lines.insert(settings_index + 1, '')
        else:
            # No settings block, add at end
            final_lines.append(item_line)
            final_lines.append('')

    file_path.write_text('\n'.join(final_lines), encoding='utf-8')


def _extract_item_name(line: str) -> str:
    """
    Extract item name from a checkbox line.
    Handles both wikilinks and plain text.

    Args:
        line: Line like "- [ ] [[WikiLink]]" or "- [ ] Plain text"

    Returns:
        Item name (wikilink name without brackets, or plain text)
    """
    line = line.strip()

    # Check for checkbox syntax
    if not line.startswith('- [ ]'):
        return ''

    # Remove checkbox part
    content = line[5:].strip()

    # Extract wikilink if present
    wikilink_match = re.match(r'\[\[([^\]]+)\]\]', content)
    if wikilink_match:
        return wikilink_match.group(1)

    # Return plain text
    return content
