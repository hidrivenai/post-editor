import pytest
from obsidian import (
    read_post_card, extract_wikilinks, update_post_card_section,
    parse_reviews, mark_review_applied, append_history_entry,
)


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

SAMPLE_CARD_WITH_REVIEWS = """# Agent
Write about AI.

# Relevant notes

# Relevant links

# Post
[[My Post]]
# Reviews
## Round 1
Status: Ready
- The intro is too generic
- Add a personal anecdote

## Round 2
Status: Applied
- Fixed the conclusion
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


class TestParseReviews:
    def test_parses_rounds(self):
        reviews = parse_reviews(SAMPLE_CARD_WITH_REVIEWS)
        assert len(reviews) == 2

    def test_round_names(self):
        reviews = parse_reviews(SAMPLE_CARD_WITH_REVIEWS)
        assert reviews[0]['name'] == 'Round 1'
        assert reviews[1]['name'] == 'Round 2'

    def test_round_statuses(self):
        reviews = parse_reviews(SAMPLE_CARD_WITH_REVIEWS)
        assert reviews[0]['status'] == 'Ready'
        assert reviews[1]['status'] == 'Applied'

    def test_round_feedback(self):
        reviews = parse_reviews(SAMPLE_CARD_WITH_REVIEWS)
        assert '- The intro is too generic' in reviews[0]['feedback']
        assert '- Add a personal anecdote' in reviews[0]['feedback']

    def test_no_reviews(self):
        assert parse_reviews(SAMPLE_POST_CARD) == []

    def test_no_reviews_section(self):
        assert parse_reviews('# Agent\nSomething\n') == []


class TestMarkReviewApplied:
    def test_marks_ready_as_applied(self):
        result = mark_review_applied(SAMPLE_CARD_WITH_REVIEWS, 'Round 1')
        reviews = parse_reviews(result)
        assert reviews[0]['status'] == 'Applied'

    def test_preserves_already_applied(self):
        result = mark_review_applied(SAMPLE_CARD_WITH_REVIEWS, 'Round 1')
        reviews = parse_reviews(result)
        assert reviews[1]['status'] == 'Applied'

    def test_preserves_feedback(self):
        result = mark_review_applied(SAMPLE_CARD_WITH_REVIEWS, 'Round 1')
        reviews = parse_reviews(result)
        assert '- The intro is too generic' in reviews[0]['feedback']

    def test_only_changes_target_round(self):
        content = SAMPLE_CARD_WITH_REVIEWS.replace(
            '## Round 2\nStatus: Applied', '## Round 2\nStatus: Ready'
        )
        result = mark_review_applied(content, 'Round 1')
        reviews = parse_reviews(result)
        assert reviews[0]['status'] == 'Applied'
        assert reviews[1]['status'] == 'Ready'


class TestReadPostCardHistory:
    def test_empty_history(self):
        card = read_post_card(SAMPLE_POST_CARD)
        assert card['History'] == ''

    def test_parses_history(self):
        content = SAMPLE_POST_CARD + "\n# History\n## 2026-03-11 Generated\nFramework: narrative\n"
        card = read_post_card(content)
        assert '2026-03-11 Generated' in card['History']
        assert 'Framework: narrative' in card['History']


class TestAppendHistoryEntry:
    def test_adds_history_to_card_without_section(self):
        result = append_history_entry(SAMPLE_POST_CARD, '## 2026-03-11 Generated\nFramework: narrative')
        assert '# History' in result
        assert '2026-03-11 Generated' in result
        assert 'Framework: narrative' in result

    def test_appends_to_existing_history(self):
        content = SAMPLE_POST_CARD + "\n# History\n## 2026-03-10 Generated\nOld entry\n"
        result = append_history_entry(content, '## 2026-03-11 Review applied: Round 1')
        card = read_post_card(result)
        assert 'Old entry' in card['History']
        assert 'Review applied: Round 1' in card['History']

    def test_preserves_other_sections(self):
        result = append_history_entry(SAMPLE_POST_CARD, '## 2026-03-11 Generated')
        card = read_post_card(result)
        assert 'Write a blog post' in card['Agent']
        assert card['Relevant notes'] == ['Note About Agents', 'AI Research Summary']
