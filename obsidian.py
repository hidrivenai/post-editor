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
        'Reviews': [],
        'History': '',
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


def parse_reviews(post_card_content: str) -> list[dict]:
    """Parse the Reviews section into structured review rounds.

    Expected format:
        # Reviews
        ## Round 1
        Status: Ready
        - Feedback point one
        - Feedback point two

        ## Round 2
        Status: Applied
        - Old feedback

    Returns list of dicts: [{'name': 'Round 1', 'status': 'Ready', 'feedback': '...'}]
    """
    # Extract raw Reviews section content
    lines = post_card_content.split('\n')
    in_reviews = False
    reviews_lines = []

    for line in lines:
        if re.match(r'^# Reviews\s*$', line):
            in_reviews = True
            continue
        elif in_reviews and re.match(r'^# ', line):
            break
        elif in_reviews:
            reviews_lines.append(line)

    if not reviews_lines:
        return []

    # Split into rounds by H2 headers
    rounds = []
    current_name = None
    current_lines = []

    for line in reviews_lines:
        h2_match = re.match(r'^## (.+)$', line)
        if h2_match:
            if current_name:
                rounds.append(_parse_single_review(current_name, current_lines))
            current_name = h2_match.group(1).strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)

    if current_name:
        rounds.append(_parse_single_review(current_name, current_lines))

    return rounds


def _parse_single_review(name: str, lines: list[str]) -> dict:
    """Parse a single review round's lines into a dict."""
    status = ''
    feedback_lines = []

    for line in lines:
        status_match = re.match(r'^Status:\s*(.+)$', line, re.IGNORECASE)
        if status_match:
            status = status_match.group(1).strip()
        elif line.strip():
            feedback_lines.append(line)

    return {
        'name': name,
        'status': status,
        'feedback': '\n'.join(feedback_lines).strip(),
    }


def mark_review_applied(post_card_content: str, round_name: str) -> str:
    """Change a review round's status from Ready to Applied."""
    lines = post_card_content.split('\n')
    result = []
    in_target_round = False

    for line in lines:
        if re.match(rf'^## {re.escape(round_name)}\s*$', line):
            in_target_round = True
            result.append(line)
        elif re.match(r'^## ', line) or re.match(r'^# ', line):
            in_target_round = False
            result.append(line)
        elif in_target_round and re.match(r'^Status:\s*Ready\s*$', line, re.IGNORECASE):
            result.append('Status: Applied')
        else:
            result.append(line)

    return '\n'.join(result)


def append_history_entry(post_card_content: str, entry: str) -> str:
    """Append a timestamped entry to the History section."""
    card = read_post_card(post_card_content)
    current = card.get('History', '')
    if current:
        new_history = current + '\n\n' + entry
    else:
        new_history = entry
    return update_post_card_section(post_card_content, 'History', new_history)


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
