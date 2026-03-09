import json
import subprocess
import pytest
import rclone_ops


@pytest.fixture(autouse=True)
def reset_cache():
    rclone_ops.reset_env_cache()
    yield
    rclone_ops.reset_env_cache()


class TestStripQuotes:
    def test_double_quotes(self):
        assert rclone_ops._strip_quotes('"hello"') == 'hello'

    def test_single_quotes(self):
        assert rclone_ops._strip_quotes("'hello'") == 'hello'

    def test_no_quotes(self):
        assert rclone_ops._strip_quotes('hello') == 'hello'

    def test_escaped_quotes(self):
        assert rclone_ops._strip_quotes('"he\\"llo"') == 'he"llo'

    def test_double_escaped(self):
        # Input: "a\\"b" → strip quotes → a\\"b → unescape → a"b
        assert rclone_ops._strip_quotes('"a\\\\\\"b"') == 'a"b'


class TestCleanRcloneEnv:
    def test_cleans_rclone_config_vars(self, monkeypatch):
        monkeypatch.setenv('RCLONE_CONFIG_GDRIVE_TOKEN', '"{\\"key\\":\\"val\\"}"')
        monkeypatch.setenv('OTHER_VAR', '"keep quotes"')
        env = rclone_ops._clean_rclone_env()
        assert env['RCLONE_CONFIG_GDRIVE_TOKEN'] == '{"key":"val"}'
        assert env['OTHER_VAR'] == '"keep quotes"'

    def test_caches_result(self, monkeypatch):
        monkeypatch.setenv('RCLONE_CONFIG_GDRIVE_TYPE', 'drive')
        env1 = rclone_ops._clean_rclone_env()
        env2 = rclone_ops._clean_rclone_env()
        assert env1 is env2


class TestListFiles:
    def test_returns_files(self, monkeypatch):
        lsjson_output = json.dumps([
            {'Name': 'a.md', 'ModTime': '2026-01-01T00:00:00Z', 'IsDir': False},
            {'Name': 'subdir', 'ModTime': '2026-01-01T00:00:00Z', 'IsDir': True},
            {'Name': 'b.md', 'ModTime': '2026-01-02T00:00:00Z', 'IsDir': False},
        ])
        monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 0, stdout=lsjson_output, stderr=''))
        files = rclone_ops.list_files('gdrive:Test')
        assert len(files) == 2
        assert files[0]['name'] == 'a.md'
        assert files[1]['name'] == 'b.md'

    def test_raises_on_failure(self, monkeypatch):
        monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 1, stdout='', stderr='error'))
        with pytest.raises(RuntimeError, match='rclone lsjson failed'):
            rclone_ops.list_files('gdrive:Test')


class TestListFilesRecursive:
    def test_returns_files_with_path(self, monkeypatch):
        lsjson_output = json.dumps([
            {'Name': 'a.md', 'Path': 'a.md', 'ModTime': '2026-01-01T00:00:00Z', 'IsDir': False},
            {'Name': 'b.md', 'Path': 'sub/b.md', 'ModTime': '2026-01-02T00:00:00Z', 'IsDir': False},
            {'Name': 'sub', 'Path': 'sub', 'ModTime': '2026-01-01T00:00:00Z', 'IsDir': True},
        ])
        monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 0, stdout=lsjson_output, stderr=''))
        files = rclone_ops.list_files_recursive('gdrive:Test')
        assert len(files) == 2
        assert files[0]['path'] == 'a.md'
        assert files[1]['path'] == 'sub/b.md'


class TestDownloadFile:
    def test_success(self, monkeypatch):
        calls = []
        def mock_run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')
        monkeypatch.setattr(subprocess, 'run', mock_run)
        rclone_ops.download_file('gdrive:Test', 'file.md', '/tmp/file.md')
        assert 'gdrive:Test/file.md' in calls[0]

    def test_raises_on_failure(self, monkeypatch):
        monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 1, stdout='', stderr='download error'))
        with pytest.raises(RuntimeError, match='rclone download failed'):
            rclone_ops.download_file('gdrive:Test', 'file.md', '/tmp/file.md')


class TestUploadFile:
    def test_success(self, monkeypatch):
        calls = []
        def mock_run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')
        monkeypatch.setattr(subprocess, 'run', mock_run)
        rclone_ops.upload_file('/tmp/file.md', 'gdrive:Test', 'file.md')
        assert 'gdrive:Test/file.md' in calls[0]

    def test_raises_on_failure(self, monkeypatch):
        monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 1, stdout='', stderr='upload error'))
        with pytest.raises(RuntimeError, match='rclone upload failed'):
            rclone_ops.upload_file('/tmp/file.md', 'gdrive:Test', 'file.md')
