import pytest
from kanban import parse_kanban, get_items_by_status, move_item, _extract_item_name


SAMPLE_KANBAN = """---
kanban-plugin: basic
---

## Ideas

- [ ] [[Idea One]]
- [ ] [[Idea Two]]

## WIP

- [ ] [[Active Post]]

## Review

## Done

- [ ] [[Old Post]]

%% kanban:settings
{"kanban-plugin":"basic"}
%%"""


class TestParseKanban:
    def test_parses_sections(self):
        result = parse_kanban(SAMPLE_KANBAN)
        assert 'Ideas' in result
        assert 'WIP' in result
        assert 'Review' in result
        assert 'Done' in result

    def test_parses_items(self):
        result = parse_kanban(SAMPLE_KANBAN)
        assert result['Ideas'] == ['Idea One', 'Idea Two']
        assert result['WIP'] == ['Active Post']
        assert result['Review'] == []
        assert result['Done'] == ['Old Post']

    def test_stops_at_settings(self):
        content = "## Section\n- [ ] Item\n%% kanban:settings\n{}\n%%"
        result = parse_kanban(content)
        assert result['Section'] == ['Item']

    def test_empty_content(self):
        assert parse_kanban('') == {}


class TestGetItemsByStatus:
    def test_returns_items(self):
        d = {'WIP': ['A', 'B'], 'Done': ['C']}
        assert get_items_by_status(d, 'WIP') == ['A', 'B']

    def test_missing_status(self):
        assert get_items_by_status({}, 'WIP') == []


class TestMoveItem:
    def test_moves_item(self):
        result = move_item(SAMPLE_KANBAN, 'Active Post', 'WIP', 'Review')
        parsed = parse_kanban(result)
        assert 'Active Post' not in parsed.get('WIP', [])
        assert 'Active Post' in parsed['Review']

    def test_preserves_other_items(self):
        result = move_item(SAMPLE_KANBAN, 'Active Post', 'WIP', 'Review')
        parsed = parse_kanban(result)
        assert parsed['Ideas'] == ['Idea One', 'Idea Two']
        assert parsed['Done'] == ['Old Post']

    def test_item_not_found_raises(self):
        with pytest.raises(ValueError, match='not found'):
            move_item(SAMPLE_KANBAN, 'Missing', 'WIP', 'Review')

    def test_move_to_section_with_settings(self):
        # Move item to the last section before settings block
        content = "## A\n- [ ] Item\n\n## B\n\n%% kanban:settings\n{}\n%%"
        result = move_item(content, 'Item', 'A', 'B')
        parsed = parse_kanban(result)
        assert 'Item' not in parsed.get('A', [])
        assert 'Item' in parsed['B']


class TestExtractItemName:
    def test_wikilink(self):
        assert _extract_item_name('- [ ] [[My Note]]') == 'My Note'

    def test_plain_text(self):
        assert _extract_item_name('- [ ] Plain text item') == 'Plain text item'

    def test_not_checkbox(self):
        assert _extract_item_name('- [x] Done') == ''

    def test_empty_line(self):
        assert _extract_item_name('') == ''
