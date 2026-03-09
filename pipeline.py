"""Per-item pipeline orchestration — adapted from writer.py."""

import logging
import re
import shutil
import subprocess

import kanban
import obsidian
import vault_io

log = logging.getLogger(__name__)


# ── Pure functions ──────────────────────────────────────────────


def extract_framework_from_prompt(agent_prompt: str) -> str | None:
    """Extract framework name from Agent prompt if specified."""
    match = re.search(r'framework:\s*["\']?([^"\'\n]+?)["\']?\s*(?:\n|$)', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'(?:use|follow)\s+(?:the\s+)?([a-zA-Z_]+)\s+framework', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_style_from_prompt(agent_prompt: str) -> str | None:
    """Extract style name from Agent prompt if specified."""
    match = re.search(r'(?:style|tone):\s*["\']?([^"\'\n]+?)["\']?\s*(?:\n|$)', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'([a-zA-Z_]+)\s+(?:style|tone)', agent_prompt, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def format_notes(notes_content: list[dict]) -> str:
    """Format list of note dicts into readable text."""
    if not notes_content:
        return "(No relevant notes)"
    formatted = []
    for note in notes_content:
        formatted.append(f"## {note['name']}\n")
        formatted.append(note['content'])
        formatted.append("\n---\n")
    return '\n'.join(formatted)


def format_links(links: list[str]) -> str:
    """Format list of URLs into readable text."""
    if not links:
        return "(No relevant links)"
    return '\n'.join(f"- {link}" for link in links)


# ── Claude CLI integration ──────────────────────────────────────


def select_framework(card: dict, context: dict, local_vault_dir: str) -> str:
    """Select writing framework — from Agent prompt or via claude -p."""
    framework = extract_framework_from_prompt(card.get('Agent', ''))
    if framework:
        return framework

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
        capture_output=True, text=True, cwd=local_vault_dir
    )

    if result.returncode != 0:
        log.error(f"Framework selection failed: {result.stderr}")
        return "narrative"

    output = result.stdout.strip()
    if not output:
        log.warning("Empty output from framework selection, using 'narrative'")
        return "narrative"

    last_line = output.split('\n')[-1].strip()
    if 'Selected framework:' in last_line:
        return last_line.split('Selected framework:')[-1].strip()
    return last_line


def select_style(card: dict, context: dict, local_vault_dir: str) -> str:
    """Select style — from Agent prompt or via claude -p."""
    style = extract_style_from_prompt(card.get('Agent', ''))
    if style:
        return style

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
        capture_output=True, text=True, cwd=local_vault_dir
    )

    if result.returncode != 0:
        log.error(f"Style selection failed: {result.stderr}")
        return "casual"

    output = result.stdout.strip()
    if not output:
        log.warning("Empty output from style selection, using 'casual'")
        return "casual"

    last_line = output.split('\n')[-1].strip()
    if 'Selected style:' in last_line:
        return last_line.split('Selected style:')[-1].strip()
    return last_line


def generate_blog_post(context: dict, framework: str, style: str,
                       local_vault_dir: str) -> str:
    """Call claude -p to generate blog post with specified framework and style."""
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
        capture_output=True, text=True, cwd=local_vault_dir
    )

    if result.returncode != 0:
        log.error(f"Blog post generation failed: {result.stderr}")
        return "# Error\n\nFailed to generate blog post."

    output = result.stdout.strip()
    if not output:
        log.warning("Empty output from blog post generation")
        return "# Error\n\nEmpty output from blog post generation."

    return output


# ── Orchestration ───────────────────────────────────────────────


def process_item(item_wikilink: str, cfg: dict, vault_index: dict) -> None:
    """Full per-item pipeline: read card → gather context → generate → upload."""
    tmp_dir = None
    try:
        # 1. Resolve wikilink → download post card
        rel_path = vault_io.resolve_wikilink(vault_index, item_wikilink)
        if not rel_path:
            log.error(f"Post card not found for '{item_wikilink}'")
            return

        card_content = vault_io.download_text(cfg, rel_path)
        card = obsidian.read_post_card(card_content)

        # 2. Build context: download relevant notes
        context = {
            'agent_prompt': card.get('Agent', ''),
            'notes_content': [],
            'links': card.get('Relevant links', []),
        }

        note_paths = []
        for note_link in card.get('Relevant notes', []):
            note_rel = vault_io.resolve_wikilink(vault_index, note_link)
            if note_rel:
                note_content = vault_io.download_text(cfg, note_rel)
                context['notes_content'].append({
                    'name': note_link,
                    'content': note_content,
                })
                note_paths.append(note_rel)
            else:
                log.warning(f"Referenced note not found: {note_link}")

        # 3. Sync vault subset for Claude
        tmp_dir = vault_io.sync_for_claude(
            cfg, vault_index,
            needed_dirs=['writing_frameworks', 'styles'],
            needed_notes=note_paths,
        )

        # 4. Select framework + style
        framework = select_framework(card, context, str(tmp_dir))
        log.info(f"Framework: {framework}")

        style = select_style(card, context, str(tmp_dir))
        log.info(f"Style: {style}")

        # 5. Generate blog post
        blog_post_content = generate_blog_post(context, framework, style, str(tmp_dir))
        log.info(f"Generated post: {len(blog_post_content)} chars")

        # 6. Upload post
        post_title = f"{item_wikilink} Post"
        vault_io.upload_text(cfg, f"{post_title}.md", blog_post_content)

        # 7. Update post card
        updated_card = obsidian.update_post_card_section(
            card_content, 'Post', f"[[{post_title}]]"
        )
        vault_io.upload_text(cfg, rel_path, updated_card)

        # 8. Move item in Kanban
        kanban_content = vault_io.download_text(cfg, "projects/Post Kanban.md")
        updated_kanban = kanban.move_item(
            kanban_content, item_wikilink, 'WIP', 'Review'
        )
        vault_io.upload_text(cfg, "projects/Post Kanban.md", updated_kanban)

        log.info(f"Successfully processed: {item_wikilink}")

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
