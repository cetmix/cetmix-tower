from .common import CommonTest


class TestSource(CommonTest):
    """Test class for git source."""

    def test_source_git_aggregator_prepare_record(self):
        """Test if source prepare record method works correctly."""

        # -- 1 --
        # Source 1
        expected_result = {
            "remotes": {
                "remote_1": "https://github.com/cetmix/cetmix-tower.git",
                "remote_2": "https://gitlab.com/cetmix/cetmix-tower.git",
                "remote_3": "git@my.gitlab.org:cetmix/cetmix-tower.git",
            },
            "merges": [
                {"remote": "remote_1", "ref": "refs/pull/123/head"},
                {"remote": "remote_2", "ref": "main"},
                {"remote": "remote_3", "ref": "10000000"},
            ],
            "target": "remote_1",
        }
        prepared_result = self.git_source_1._git_aggregator_prepare_record()
        self.assertEqual(
            prepared_result, expected_result, "Prepared result is not correct"
        )

        # -- 2 --
        # Source 2
        expected_result = {
            "remotes": {
                "remote_1": "https://bitbucket.org/cetmix/cetmix-tower.git",
                "remote_2": "git@other.com:cetmix/cetmix-tower.git",
            },
            "merges": [
                {"remote": "remote_1", "ref": "dev"},
                {"remote": "remote_2", "ref": "old"},
            ],
            "target": "remote_1",
        }
