#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""Agent Writer Pipeline - Generate blog posts from WIP post cards."""

import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.kanban import parse_kanban, get_items_by_status, move_item
from utils.obsidian import (
    read_note,
    read_post_card,
    extract_wikilinks,
    create_blog_post,
    update_post_card_section,
    resolve_wikilink
)

# Configuration
VAULT_PATH = Path(__file__).parent.parent / "hidrivenai_obsidian"
KANBAN_PATH = VAULT_PATH / "projects/Post Kanban.md"


def main():
    """Main entry point for the writer pipeline."""
    print("=" * 60)
    print("Agent Writer Pipeline - Blog Post Generation")
    print("=" * 60)
    print()

    # 1. Parse Kanban board
    print(f"Reading Kanban board: {KANBAN_PATH}")
    kanban = parse_kanban(KANBAN_PATH)
    wip_items = get_items_by_status(kanban, "WIP")

    if not wip_items:
        print("No items in WIP status. Nothing to do.")
        print()
        return

    print(f"Found {len(wip_items)} item(s) in WIP:")
    for item in wip_items:
        print(f"  - {item}")
    print()

    # 2. Process each WIP item
    for item_wikilink in wip_items:
        print(f"{'=' * 60}")
        print(f"Processing: {item_wikilink}")
        print(f"{'=' * 60}")

        try:
            # 3. Read post card
            post_card_path = resolve_wikilink(VAULT_PATH, item_wikilink)
            if not post_card_path:
                print(f"  ERROR: Post card file not found for '{item_wikilink}'")
                print()
                continue

            print(f"  Reading post card: {post_card_path.name}")
            card = read_post_card(post_card_path)

            # 4. Gather context
            print(f"  Gathering context...")
            context = build_context(card)
            print(f"    - Agent prompt: {len(context['agent_prompt'])} chars")
            print(f"    - Relevant notes: {len(context['notes_content'])} note(s)")
            print(f"    - Relevant links: {len(context['links'])} link(s)")

            # 5. Select writing framework
            print(f"  Selecting writing framework...")
            framework = select_framework(card, context)
            print(f"    → Framework: {framework}")

            # 6. Select style
            print(f"  Selecting style...")
            style = select_style(card, context)
            print(f"    → Style: {style}")

            # 7. Generate blog post with framework and style
            print(f"  Generating blog post...")
            blog_post_content = generate_blog_post(context, framework, style)
            print(f"    → Generated: {len(blog_post_content)} chars")

            # 8. Create blog post file
            post_title = f"{item_wikilink} Post"
            print(f"  Creating blog post file: {post_title}.md")
            post_path = create_blog_post(VAULT_PATH, post_title, blog_post_content)

            # 9. Update post card with link to post
            # Use the actual filename that was created (might have a number appended)
            actual_post_name = post_path.stem  # Get filename without .md extension
            print(f"  Updating post card...")
            update_post_card_section(post_card_path, "Post", f"[[{actual_post_name}]]")

            # 10. Move to Review in Kanban
            print(f"  Moving to Review in Kanban...")
            move_item(KANBAN_PATH, item_wikilink, "WIP", "Review")

            print()
            print(f"✓ Successfully created: {actual_post_name}")
            print(f"  File: {post_path}")
            print()

        except Exception as e:
            print(f"  ERROR: Failed to process '{item_wikilink}': {e}")
            print()
            continue

    print("=" * 60)
    print("Pipeline complete!")
    print("=" * 60)


def build_context(card: Dict) -> Dict:
    """
    Gather all relevant notes and links from post card.

    Args:
        card: Post card dict from read_post_card()

    Returns:
        Dict with 'agent_prompt', 'notes_content', 'links'
    """
    context = {
        'agent_prompt': card.get('Agent', ''),
        'notes_content': [],
        'links': card.get('Relevant links', [])
    }

    # Read all relevant notes
    for note_link in card.get('Relevant notes', []):
        try:
            note_content = read_note(VAULT_PATH, note_link)
            context['notes_content'].append({
                'name': note_link,
                'content': note_content
            })
        except FileNotFoundError:
            print(f"    WARNING: Referenced note not found: {note_link}")

    return context


def extract_framework_from_prompt(agent_prompt: str) -> Optional[str]:
    """
    Extract framework name from Agent prompt if specified.

    Looks for patterns like:
    - "framework: narrative"
    - "framework: storytelling_frameworks"
    - "framework: 'Storytelling Frameworks'"
    - "use the narrative framework"
    - "follow narrative framework"

    Args:
        agent_prompt: Agent section content

    Returns:
        Framework name or None if not specified
    """
    # Pattern 1: "framework: name" (with optional quotes)
    match = re.search(r'framework:\s*["\']?([^"\'\n]+?)["\']?\s*(?:\n|$)', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 2: "use/follow the X framework" (words and underscores)
    match = re.search(r'(?:use|follow)\s+(?:the\s+)?([a-zA-Z_]+)\s+framework', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def extract_style_from_prompt(agent_prompt: str) -> Optional[str]:
    """
    Extract style name from Agent prompt if specified.

    Looks for patterns like:
    - "style: casual"
    - "style: humble_expert"
    - "tone: post_mortem_tone"
    - "style: 'Post Mortem Tone'"
    - "casual style"
    - "formal tone"

    Args:
        agent_prompt: Agent section content

    Returns:
        Style name or None if not specified
    """
    # Pattern 1: "style: name" or "tone: name" (with optional quotes)
    match = re.search(r'(?:style|tone):\s*["\']?([^"\'\n]+?)["\']?\s*(?:\n|$)', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 2: "X style" or "X tone" (words and underscores)
    match = re.search(r'([a-zA-Z_]+)\s+(?:style|tone)', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def format_notes(notes_content: List[Dict]) -> str:
    """
    Format list of note dicts into readable text.

    Args:
        notes_content: List of dicts with 'name' and 'content' keys

    Returns:
        Formatted string
    """
    if not notes_content:
        return "(No relevant notes)"

    formatted = []
    for note in notes_content:
        formatted.append(f"## {note['name']}\n")
        formatted.append(note['content'])
        formatted.append("\n---\n")

    return '\n'.join(formatted)


def format_links(links: List[str]) -> str:
    """
    Format list of URLs into readable text.

    Args:
        links: List of URL strings

    Returns:
        Formatted string
    """
    if not links:
        return "(No relevant links)"

    return '\n'.join(f"- {link}" for link in links)


def select_framework(card: Dict, context: Dict) -> str:
    """
    Select writing framework - either from Agent prompt or via claude -p.

    Args:
        card: Post card dict
        context: Context dict with agent_prompt, notes_content, links

    Returns:
        Framework name
    """
    agent_prompt = card.get('Agent', '')

    # Check if framework is specified in Agent prompt
    framework = extract_framework_from_prompt(agent_prompt)
    if framework:
        return framework

    # Otherwise, call claude -p to select framework
    # Truncate context for selection prompt
    notes_preview = format_notes(context['notes_content'])[:500]
    if len(format_notes(context['notes_content'])) > 500:
        notes_preview += "..."

    prompt = f"""You have read access to the hidrivenai_obsidian/ directory.

Your task: Select the most appropriate writing framework from the writing_frameworks/ directory.

Agent Instructions:
{context['agent_prompt']}

Topic/Context:
{notes_preview}

INSTRUCTIONS:
1. List all .md files in hidrivenai_obsidian/writing_frameworks/
2. Read each framework file to understand what it offers
3. Some files (like "storytelling_frameworks.md") contain multiple frameworks - if you choose one of these, you can reference a specific framework within it
4. Based on the agent instructions and topic, select the most appropriate framework
5. On the LAST LINE of your response, output ONLY the filename (without .md extension)
   - For files with spaces, use the exact filename: "Storytelling Frameworks" not "storytelling_frameworks"
   - For files with underscores, use the exact filename: "storytelling_frameworks" not "Storytelling Frameworks"

RESPONSE FORMAT:
[Your analysis here...]

Selected framework: <filename-without-extension>"""

    result = subprocess.run(
        ['claude', '-p', prompt, '--add-dir', 'hidrivenai_obsidian'],
        capture_output=True,
        text=True,
        cwd=VAULT_PATH.parent
    )

    # Debug output
    if result.returncode != 0:
        print(f"    ERROR: Framework selection failed with code {result.returncode}")
        print(f"    STDERR: {result.stderr}")
        return "narrative"  # Fallback

    # Extract last line as framework name
    output = result.stdout.strip()
    if not output:
        print(f"    WARNING: Empty output from framework selection, using 'narrative'")
        return "narrative"

    print(f"    DEBUG: Framework selection output ({len(output)} chars)")

    last_line = output.split('\n')[-1].strip()

    # Try to extract framework name from "Selected framework: X" format
    if 'Selected framework:' in last_line:
        framework_name = last_line.split('Selected framework:')[-1].strip()
    else:
        framework_name = last_line

    return framework_name


def select_style(card: Dict, context: Dict) -> str:
    """
    Select style - either from Agent prompt or via claude -p.

    Args:
        card: Post card dict
        context: Context dict with agent_prompt, notes_content, links

    Returns:
        Style name
    """
    agent_prompt = card.get('Agent', '')

    # Check if style is specified in Agent prompt
    style = extract_style_from_prompt(agent_prompt)
    if style:
        return style

    # Otherwise, call claude -p to select style
    # Truncate context for selection prompt
    notes_preview = format_notes(context['notes_content'])[:500]
    if len(format_notes(context['notes_content'])) > 500:
        notes_preview += "..."

    prompt = f"""You have read access to the hidrivenai_obsidian/ directory.

Your task: Select the most appropriate writing style from the styles/ directory.

Agent Instructions:
{context['agent_prompt']}

Topic/Context:
{notes_preview}

INSTRUCTIONS:
1. List all .md files in hidrivenai_obsidian/styles/
2. Read each style file to understand the tone, voice, and approach
3. Based on the agent instructions and topic, select the most appropriate style
4. On the LAST LINE of your response, output ONLY the filename (without .md extension)
   - Use exact filename with underscores: "humble_expert" or "post_mortem_tone"
   - Preserve the exact case and format from the filename

RESPONSE FORMAT:
[Your analysis here...]

Selected style: <filename-without-extension>"""

    result = subprocess.run(
        ['claude', '-p', prompt, '--add-dir', 'hidrivenai_obsidian'],
        capture_output=True,
        text=True,
        cwd=VAULT_PATH.parent
    )

    # Debug output
    if result.returncode != 0:
        print(f"    ERROR: Style selection failed with code {result.returncode}")
        print(f"    STDERR: {result.stderr}")
        return "casual"  # Fallback

    # Extract last line as style name
    output = result.stdout.strip()
    if not output:
        print(f"    WARNING: Empty output from style selection, using 'casual'")
        return "casual"

    print(f"    DEBUG: Style selection output ({len(output)} chars)")

    last_line = output.split('\n')[-1].strip()

    # Try to extract style name from "Selected style: X" format
    if 'Selected style:' in last_line:
        style_name = last_line.split('Selected style:')[-1].strip()
    else:
        style_name = last_line

    return style_name


def generate_blog_post(context: Dict, framework: str, style: str) -> str:
    """
    Call claude -p to generate blog post with specified framework and style.

    Args:
        context: Context dict with agent_prompt, notes_content, links
        framework: Framework name
        style: Style name

    Returns:
        Generated blog post content
    """
    prompt = f"""You have read access to the hidrivenai_obsidian/ folder.

Your task: Write a complete, well-structured blog post in markdown format.

CONTEXT:

Agent Instructions:
{context['agent_prompt']}

Writing Framework: {framework}
Read the framework guide at: hidrivenai_obsidian/writing_frameworks/{framework}.md

Style: {style}
Read the style guide at: hidrivenai_obsidian/styles/{style}.md

Relevant Notes:
{format_notes(context['notes_content'])}

Relevant Links:
{format_links(context['links'])}

INSTRUCTIONS:
1. Read and understand the specified framework file ({framework}.md)
2. Read and understand the specified style file ({style}.md)
3. Review all relevant notes and links provided above
4. Generate a blog post that:
   - Follows the structure and approach defined in the framework
   - Adopts the tone, voice, and language patterns defined in the style
   - Addresses the topic/requirements in the Agent Instructions
   - Incorporates insights from the relevant notes
   - References or builds upon the relevant links where appropriate

5. The output should be:
   - Complete markdown (ready to publish)
   - Well-structured with appropriate headings
   - Engaging and valuable to readers
   - Consistent with both the framework and style guidelines

OUTPUT FORMAT:
Return ONLY the blog post content in markdown format. Do not include any preamble or meta-commentary."""

    result = subprocess.run(
        ['claude', '-p', prompt, '--add-dir', 'hidrivenai_obsidian'],
        capture_output=True,
        text=True,
        cwd=VAULT_PATH.parent
    )

    # Debug output
    if result.returncode != 0:
        print(f"    ERROR: Blog post generation failed with code {result.returncode}")
        print(f"    STDERR: {result.stderr}")
        return "# Error\n\nFailed to generate blog post."

    output = result.stdout.strip()
    if not output:
        print(f"    WARNING: Empty output from blog post generation")
        print(f"    STDERR: {result.stderr}")
        return "# Error\n\nEmpty output from blog post generation."

    print(f"    DEBUG: Blog post generation output ({len(output)} chars)")

    return output


if __name__ == "__main__":
    main()
