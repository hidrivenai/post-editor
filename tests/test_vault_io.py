import os
import pytest
from unittest.mock import patch, call
from pathlib import Path

import vault_io


SAMPLE_ENTRIES = [
    {'name': 'note1.md', 'path': 'note1.md', 'mod_time': '2026-01-01T00:00:00Z'},
    {'name': 'note2.md', 'path': 'projects/note2.md', 'mod_time': '2026-01-02T00:00:00Z'},
    {'name': 'fw.md', 'path': 'writing_frameworks/fw.md', 'mod_time': '2026-01-01T00:00:00Z'},
    {'name': 'style.md', 'path': 'styles/style.md', 'mod_time': '2026-01-01T00:00:00Z'},
    {'name': 'image.png', 'path': 'attachments/image.png', 'mod_time': '2026-01-01T00:00:00Z'},
]

CFG = {'gdrive_remote': 'gdrive:Test/Vault'}


class TestBuildVaultIndex:
    @patch('vault_io.list_files_recursive', return_value=SAMPLE_ENTRIES)
    def test_builds_index_md_only(self, mock_list):
        index = vault_io.build_vault_index(CFG)
        assert index == {
            'note1': 'note1.md',
            'note2': 'projects/note2.md',
            'fw': 'writing_frameworks/fw.md',
            'style': 'styles/style.md',
        }
        mock_list.assert_called_once_with('gdrive:Test/Vault')


class TestDownloadText:
    @patch('vault_io.download_file')
    def test_returns_file_content(self, mock_dl, tmp_path):
        def write_content(remote, filename, local_path):
            with open(local_path, 'w') as f:
                f.write('# Hello\nWorld')
        mock_dl.side_effect = write_content

        content = vault_io.download_text(CFG, 'note1.md')
        assert content == '# Hello\nWorld'


class TestUploadText:
    @patch('vault_io.upload_file')
    def test_uploads_content(self, mock_ul):
        vault_io.upload_text(CFG, 'output.md', '# Post Content')
        mock_ul.assert_called_once()
        args = mock_ul.call_args
        # Verify the tmp file was created and remote path is correct
        assert args[0][1] == 'gdrive:Test/Vault'
        assert args[0][2] == 'output.md'


class TestResolveWikilink:
    def test_found(self):
        index = {'note1': 'note1.md', 'note2': 'projects/note2.md'}
        assert vault_io.resolve_wikilink(index, 'note2') == 'projects/note2.md'

    def test_not_found(self):
        index = {'note1': 'note1.md'}
        assert vault_io.resolve_wikilink(index, 'missing') is None


class TestSyncForClaude:
    @patch('vault_io.download_file')
    def test_downloads_dirs_and_notes(self, mock_dl):
        vault_index = {
            'fw': 'writing_frameworks/fw.md',
            'narrative': 'writing_frameworks/narrative.md',
            'style': 'styles/style.md',
            'note1': 'note1.md',
            'note2': 'projects/note2.md',
        }
        tmp_dir = vault_io.sync_for_claude(
            CFG, vault_index,
            needed_dirs=['writing_frameworks', 'styles'],
            needed_notes=['note1.md'],
        )
        try:
            assert tmp_dir.exists()
            # Should download 2 framework files + 1 style + 1 note = 4 calls
            assert mock_dl.call_count == 4
            downloaded_files = [c[0][1] for c in mock_dl.call_args_list]
            assert 'writing_frameworks/fw.md' in downloaded_files
            assert 'writing_frameworks/narrative.md' in downloaded_files
            assert 'styles/style.md' in downloaded_files
            assert 'note1.md' in downloaded_files
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @patch('vault_io.download_file')
    def test_creates_subdirectories(self, mock_dl):
        vault_index = {'fw': 'writing_frameworks/fw.md'}
        tmp_dir = vault_io.sync_for_claude(CFG, vault_index, ['writing_frameworks'], [])
        try:
            fw_dir = tmp_dir / 'hidrivenai_obsidian' / 'writing_frameworks'
            assert fw_dir.exists()
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
