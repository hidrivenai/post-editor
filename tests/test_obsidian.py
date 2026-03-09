import pytest
from obsidian import read_post_card, extract_wikilinks, update_post_card_section


SAMPLE_POST_CARD = """# Agent
Write a blog post about AI agents.
framework: narrative
style: casual

# Relevant notes
- [[Note About Agents]]
- [[AI Research Summary]]

# Relevant links
- [OpenAI Blog](https://openai.com/blog)
- https://example.com/article

# Post

# Reviews
"""


class TestReadPostCard:
    def test_parses_agent_section(self):
        card = read_post_card(SAMPLE_POST_CARD)
        assert 'framework: narrative' in card['Agent']
        assert 'Write a blog post' in card['Agent']

    def test_parses_notes_as_list(self):
        card = read_post_card(SAMPLE_POST_CARD)
        assert card['Relevant notes'] == ['Note About Agents', 'AI Research Summary']

    def test_parses_links(self):
        card = read_post_card(SAMPLE_POST_CARD)
        assert 'https://openai.com/blog' in card['Relevant links']
        assert 'https://example.com/article' in card['Relevant links']

    def test_empty_sections(self):
        card = read_post_card(SAMPLE_POST_CARD)
        assert card['Post'] == ''
        assert card['Reviews'] == []

    def test_empty_content(self):
        card = read_post_card('')
        assert card['Agent'] == ''
        assert card['Relevant notes'] == []


class TestExtractWikilinks:
    def test_extracts_links(self):
        content = "See [[Note A]] and [[Note B]] for details."
        assert extract_wikilinks(content) == ['Note A', 'Note B']

    def test_no_links(self):
        assert extract_wikilinks('No links here') == []

    def test_nested_brackets(self):
        assert extract_wikilinks('[[Simple]]') == ['Simple']


class TestUpdatePostCardSection:
    def test_updates_existing_section(self):
        result = update_post_card_section(SAMPLE_POST_CARD, 'Post', '[[My New Post]]')
        card = read_post_card(result)
        assert '[[My New Post]]' in card['Post']

    def test_preserves_other_sections(self):
        result = update_post_card_section(SAMPLE_POST_CARD, 'Post', '[[My Post]]')
        card = read_post_card(result)
        assert 'Write a blog post' in card['Agent']
        assert card['Relevant notes'] == ['Note About Agents', 'AI Research Summary']

    def test_adds_missing_section(self):
        content = "# Agent\nDo something\n"
        result = update_post_card_section(content, 'Post', '[[New Post]]')
        assert '# Post' in result
        assert '[[New Post]]' in result

    def test_replaces_existing_content(self):
        content = "# Post\nOld content\n# Reviews\n"
        result = update_post_card_section(content, 'Post', 'New content')
        assert 'Old content' not in result
        assert 'New content' in result
        assert '# Reviews' in result
