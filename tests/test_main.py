import pytest
from unittest.mock import patch, MagicMock

import main


SAMPLE_KANBAN = """## Ideas

## WIP
- [ ] [[Post A]]
- [ ] [[Post B]]

## Review

## Done
"""


class TestRunOnce:
    @patch('main.pipeline')
    @patch('main.vault_io')
    def test_processes_wip_items(self, mock_vio, mock_pipeline):
        mock_vio.build_vault_index.return_value = {'Post A': 'a.md', 'Post B': 'b.md'}
        mock_vio.download_text.return_value = SAMPLE_KANBAN

        cfg = {'gdrive_remote': 'gdrive:Test'}
        main.run_once(cfg)

        assert mock_pipeline.process_item.call_count == 2
        mock_pipeline.process_item.assert_any_call('Post A', cfg, {'Post A': 'a.md', 'Post B': 'b.md'})
        mock_pipeline.process_item.assert_any_call('Post B', cfg, {'Post A': 'a.md', 'Post B': 'b.md'})

    @patch('main.pipeline')
    @patch('main.vault_io')
    def test_no_wip_items(self, mock_vio, mock_pipeline):
        mock_vio.build_vault_index.return_value = {}
        mock_vio.download_text.return_value = "## WIP\n\n## Review\n"

        main.run_once({'gdrive_remote': 'gdrive:Test'})
        mock_pipeline.process_item.assert_not_called()

    @patch('main.pipeline')
    @patch('main.vault_io')
    def test_continues_on_item_error(self, mock_vio, mock_pipeline):
        mock_vio.build_vault_index.return_value = {'A': 'a.md', 'B': 'b.md'}
        mock_vio.download_text.return_value = "## WIP\n- [ ] [[A]]\n- [ ] [[B]]\n"
        mock_pipeline.process_item.side_effect = [Exception("fail"), None]

        main.run_once({'gdrive_remote': 'gdrive:Test'})
        assert mock_pipeline.process_item.call_count == 2


class TestMain:
    @patch('main.time.sleep', side_effect=KeyboardInterrupt)
    @patch('main.run_once')
    @patch('main.load_config', return_value={'poll_interval': 60, 'gdrive_remote': 'g'})
    def test_calls_run_once_then_sleeps(self, mock_cfg, mock_run, mock_sleep):
        with pytest.raises(KeyboardInterrupt):
            main.main()
        mock_run.assert_called_once()
        mock_sleep.assert_called_once_with(60)
