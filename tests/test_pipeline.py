import subprocess
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

import pipeline


class TestExtractFrameworkFromPrompt:
    def test_explicit_framework(self):
        assert pipeline.extract_framework_from_prompt('framework: narrative\nother stuff') == 'narrative'

    def test_quoted_framework(self):
        assert pipeline.extract_framework_from_prompt("framework: 'Storytelling Frameworks'") == 'Storytelling Frameworks'

    def test_use_pattern(self):
        assert pipeline.extract_framework_from_prompt('use the narrative framework') == 'narrative'

    def test_follow_pattern(self):
        assert pipeline.extract_framework_from_prompt('follow storytelling_frameworks framework') == 'storytelling_frameworks'

    def test_no_framework(self):
        assert pipeline.extract_framework_from_prompt('just write something') is None

    def test_case_insensitive(self):
        assert pipeline.extract_framework_from_prompt('Framework: Narrative') == 'Narrative'


class TestExtractStyleFromPrompt:
    def test_explicit_style(self):
        assert pipeline.extract_style_from_prompt('style: casual') == 'casual'

    def test_tone_keyword(self):
        assert pipeline.extract_style_from_prompt('tone: post_mortem_tone') == 'post_mortem_tone'

    def test_style_pattern(self):
        assert pipeline.extract_style_from_prompt('use casual style') == 'casual'

    def test_no_style(self):
        assert pipeline.extract_style_from_prompt('just write something') is None


class TestCleanPostOutput:
    def test_strips_preamble(self):
        text = "Here's the blog post:\n\n# My Post\n\nContent"
        assert pipeline._clean_post_output(text) == "# My Post\n\nContent"

    def test_strips_multiline_preamble(self):
        text = "I cannot access the web.\nI'll work from what I know.\n\n# My Post\n\nContent"
        assert pipeline._clean_post_output(text) == "# My Post\n\nContent"

    def test_no_preamble(self):
        text = "# My Post\n\nContent"
        assert pipeline._clean_post_output(text) == "# My Post\n\nContent"

    def test_no_heading(self):
        text = "Just some text without headings"
        assert pipeline._clean_post_output(text) == "Just some text without headings"


class TestSplitPostAndNotes:
    def test_no_separator(self):
        post, notes = pipeline._split_post_and_notes('# My Post\n\nContent')
        assert post == '# My Post\n\nContent'
        assert notes == ''

    def test_with_separator(self):
        output = '# My Post\n\nContent\n---NOTES---\nUsed narrative arc.'
        post, notes = pipeline._split_post_and_notes(output)
        assert post == '# My Post\n\nContent'
        assert notes == 'Used narrative arc.'

    def test_strips_whitespace(self):
        output = '  # Post  \n\n---NOTES---\n  Some notes  '
        post, notes = pipeline._split_post_and_notes(output)
        assert post == '# Post'
        assert notes == 'Some notes'

    def test_strips_preamble_with_notes(self):
        output = "Here's the post:\n\n# Title\n\nBody\n---NOTES---\nNotes here"
        post, notes = pipeline._split_post_and_notes(output)
        assert post == '# Title\n\nBody'
        assert notes == 'Notes here'


class TestFormatNotes:
    def test_formats_notes(self):
        notes = [{'name': 'Note A', 'content': 'Content A'}]
        result = pipeline.format_notes(notes)
        assert '## Note A' in result
        assert 'Content A' in result

    def test_empty_notes(self):
        assert pipeline.format_notes([]) == '(No relevant notes)'


class TestFormatLinks:
    def test_formats_links(self):
        result = pipeline.format_links(['https://a.com', 'https://b.com'])
        assert '- https://a.com' in result
        assert '- https://b.com' in result

    def test_empty_links(self):
        assert pipeline.format_links([]) == '(No relevant links)'


class TestSelectFramework:
    def test_uses_prompt_framework(self):
        card = {'Agent': 'framework: narrative'}
        result = pipeline.select_framework(card, {}, '/tmp')
        assert result == 'narrative'

    @patch('subprocess.run')
    def test_calls_claude_when_no_prompt(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout='Analysis...\nSelected framework: storytelling', stderr='')
        card = {'Agent': 'write about AI'}
        context = {'agent_prompt': 'write about AI', 'notes_content': [], 'links': []}
        result = pipeline.select_framework(card, context, '/tmp/vault')
        assert result == 'storytelling'
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert 'claude' in cmd
        assert '--add-dir' in cmd

    @patch('subprocess.run')
    def test_fallback_on_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 1, stdout='', stderr='error')
        card = {'Agent': 'write'}
        context = {'agent_prompt': 'write', 'notes_content': [], 'links': []}
        assert pipeline.select_framework(card, context, '/tmp') == 'narrative'


class TestSelectStyle:
    def test_uses_prompt_style(self):
        card = {'Agent': 'style: humble_expert'}
        result = pipeline.select_style(card, {}, '/tmp')
        assert result == 'humble_expert'

    @patch('subprocess.run')
    def test_calls_claude_when_no_prompt(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout='Analysis...\nSelected style: casual', stderr='')
        card = {'Agent': 'write about AI'}
        context = {'agent_prompt': 'write about AI', 'notes_content': [], 'links': []}
        result = pipeline.select_style(card, context, '/tmp/vault')
        assert result == 'casual'

    @patch('subprocess.run')
    def test_fallback_on_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 1, stdout='', stderr='error')
        card = {'Agent': 'write'}
        context = {'agent_prompt': 'write', 'notes_content': [], 'links': []}
        assert pipeline.select_style(card, context, '/tmp') == 'casual'


class TestGenerateBlogPost:
    @patch('subprocess.run')
    def test_returns_output(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout='# My Post\n\nContent here.', stderr='')
        context = {'agent_prompt': 'write', 'notes_content': [], 'links': []}
        result = pipeline.generate_blog_post(context, 'narrative', 'casual', '/tmp')
        assert '# My Post' in result

    @patch('subprocess.run')
    def test_error_on_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 1, stdout='', stderr='fail')
        context = {'agent_prompt': 'write', 'notes_content': [], 'links': []}
        result = pipeline.generate_blog_post(context, 'narrative', 'casual', '/tmp')
        assert 'Error' in result


class TestRevisePost:
    @patch('subprocess.run')
    def test_returns_revised_output(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout='# Revised Post\n\nBetter content.', stderr='')
        result = pipeline.revise_post('# Old Post', '- Fix intro', 'write about AI', '/tmp')
        assert '# Revised Post' in result

    @patch('subprocess.run')
    def test_returns_none_on_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 1, stdout='', stderr='fail')
        result = pipeline.revise_post('# Old Post', '- Fix intro', 'write', '/tmp')
        assert result is None


class TestProcessItemGenerate:
    @patch('pipeline.vault_io')
    @patch('subprocess.run')
    def test_generates_new_post(self, mock_run, mock_vio):
        mock_vio.resolve_wikilink.return_value = 'cards/My Post.md'
        mock_vio.download_text.side_effect = [
            # Post card content (no post yet)
            '# Agent\nframework: narrative\nstyle: casual\n\n# Relevant notes\n\n# Relevant links\n\n# Post\n\n# Reviews\n',
            # Kanban content
            '## WIP\n- [ ] [[My Post]]\n\n## Review\n\n',
        ]
        mock_vio.sync_for_claude.return_value = Path('/tmp/test_vault')
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout='# Generated Post\n\nContent', stderr='')

        cfg = {'gdrive_remote': 'gdrive:Test'}
        vault_index = {'My Post': 'cards/My Post.md'}

        pipeline.process_item('My Post', cfg, vault_index)

        upload_calls = mock_vio.upload_text.call_args_list
        assert len(upload_calls) == 3  # post file + updated card + kanban
        assert upload_calls[0][0][1] == 'My Post Post.md'
        assert upload_calls[1][0][1] == 'cards/My Post.md'
        assert upload_calls[2][0][1] == 'projects/Post Kanban.md'
        # Card includes History entry
        card_content = upload_calls[1][0][2]
        assert '# History' in card_content
        assert 'Generated' in card_content
        assert 'Framework: narrative' in card_content

    @patch('pipeline.vault_io')
    def test_skips_missing_card(self, mock_vio):
        mock_vio.resolve_wikilink.return_value = None
        pipeline.process_item('Missing', {}, {})
        mock_vio.download_text.assert_not_called()


class TestProcessItemReview:
    @patch('pipeline.vault_io')
    @patch('subprocess.run')
    def test_applies_ready_reviews(self, mock_run, mock_vio):
        card_content = (
            '# Agent\nWrite about AI.\n\n# Relevant notes\n\n# Relevant links\n\n'
            '# Post\n[[My Post Post]]\n# Reviews\n## Round 1\nStatus: Ready\n'
            '- Fix the intro\n- Add examples\n'
        )
        mock_vio.resolve_wikilink.side_effect = lambda idx, name: {
            'My Item': 'cards/My Item.md',
            'My Post Post': 'My Post Post.md',
        }.get(name)
        mock_vio.download_text.side_effect = [
            card_content,           # post card
            '# Old Post\nContent',  # current post
            '## WIP\n- [ ] [[My Item]]\n\n## Review\n\n',  # kanban
        ]
        mock_vio.sync_for_claude.return_value = Path('/tmp/test_vault')
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout='# Revised Post\n\nBetter content', stderr='')

        cfg = {'gdrive_remote': 'gdrive:Test'}
        vault_index = {'My Item': 'cards/My Item.md', 'My Post Post': 'My Post Post.md'}

        pipeline.process_item('My Item', cfg, vault_index)

        upload_calls = mock_vio.upload_text.call_args_list
        assert len(upload_calls) == 3  # revised post + updated card + kanban
        # Revised post uploaded
        assert upload_calls[0][0][1] == 'My Post Post.md'
        assert '# Revised Post' in upload_calls[0][0][2]
        # Card updated with Applied status + History
        card_content = upload_calls[1][0][2]
        assert 'Applied' in card_content
        assert '# History' in card_content
        assert 'Review applied: Round 1' in card_content
        # Kanban updated
        assert upload_calls[2][0][1] == 'projects/Post Kanban.md'

    @patch('pipeline.vault_io')
    def test_skips_when_no_ready_reviews(self, mock_vio):
        card_content = (
            '# Agent\nWrite.\n\n# Post\n[[My Post]]\n# Reviews\n'
            '## Round 1\nStatus: Applied\n- Old feedback\n'
        )
        mock_vio.resolve_wikilink.return_value = 'cards/Item.md'
        mock_vio.download_text.return_value = card_content

        pipeline.process_item('Item', {'gdrive_remote': 'g'}, {'Item': 'cards/Item.md'})

        # No uploads — nothing to do
        mock_vio.upload_text.assert_not_called()
