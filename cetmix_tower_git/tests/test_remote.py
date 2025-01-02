from odoo.exceptions import ValidationError

from .common import CommonTest


class TestRemote(CommonTest):
    """Test class for git remote."""

    def test_remote_provider_protocol_and_name(self):
        """Test if remote provider is detected correctly"""

        # -- 1--
        # GitHub + https
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_github_https.repo_provider,
            "github",
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_github_https.url_protocol,
            "https",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_github_https.name,
            "remote_1",
            "Name is not prepared correctly",
        )

        # -- 2 --
        # GitLab + ssh
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_gitlab_ssh.repo_provider,
            "gitlab",
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_gitlab_ssh.url_protocol,
            "ssh",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_gitlab_ssh.name,
            "remote_3",
            "Name is not prepared correctly",
        )

        # -- 3 --
        # Bitbucket + https
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_bitbucket_https.repo_provider,
            "bitbucket",
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_bitbucket_https.url_protocol,
            "https",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_bitbucket_https.name,
            "remote_1",
            "Name is not prepared correctly",
        )

        # -- 4 --
        # Other + ssh
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_other_ssh.repo_provider,
            "other",
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_other_ssh.url_protocol,
            "ssh",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_other_ssh.name,
            "remote_2",
            "Name is not prepared correctly",
        )

        # -- 5 --
        # Invalid trailing symbols
        with self.assertRaises(ValidationError):
            self.GitRemote.create(
                {
                    "url": "not a git@other.com:cetmix/cetmix-tower.git",
                    "source_id": self.git_source_1.id,
                    "head": "main",
                }
            )

        # -- 6 --
        # Invalid URL (does not end with .git)
        with self.assertRaises(ValidationError):
            self.GitRemote.create(
                {
                    "url": "https://other.com/cetmix/cetmix-tower",
                    "source_id": self.git_source_1.id,
                    "head": "main",
                }
            )
        # -- 7 --
        # Invalid URL (does not contain at least two parts separated by dot)
        with self.assertRaises(ValidationError):
            self.GitRemote.create(
                {
                    "url": "https://memes/cetmix/cetmix-tower",
                    "source_id": self.git_source_1.id,
                    "head": "main",
                }
            )

    def test_git_aggregator_prepare_url(self):
        """Test if url is prepared correctly"""

        # -- 1 --
        # GitHub + https
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_url(),
            self.remote_github_https.url,
            "URL is not prepared correctly",
        )

        # -- 2 --
        # GitHub + https -> private
        self.remote_github_https.is_private = True
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_url(),
            "https://$GITHUB_TOKEN:x-oauth-basic@github.com/cetmix/cetmix-tower.git",
            "URL is not prepared correctly",
        )

        # -- 3 --
        # Gitlab + https
        self.assertEqual(
            self.remote_gitlab_https._git_aggregator_prepare_url(),
            self.remote_gitlab_https.url,
            "URL is not prepared correctly",
        )

        # -- 4 --
        # Gitlab + https -> private
        self.remote_gitlab_https.is_private = True
        self.assertEqual(
            self.remote_gitlab_https._git_aggregator_prepare_url(),
            "https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@gitlab.com/cetmix/cetmix-tower.git",
            "URL is not prepared correctly",
        )

        # -- 5 --
        # Bitbucket + https
        self.assertEqual(
            self.remote_bitbucket_https._git_aggregator_prepare_url(),
            self.remote_bitbucket_https.url,
            "URL is not prepared correctly",
        )

        # -- 6 --
        # Bitbucket + https -> private
        self.remote_bitbucket_https.is_private = True
        self.assertEqual(
            self.remote_bitbucket_https._git_aggregator_prepare_url(),
            "https://x-oauth-basic:$BITBUCKET_TOKEN@bitbucket.org/cetmix/cetmix-tower.git",
            "URL is not prepared correctly",
        )

        # -- 7 --
        # Other + ssh
        self.assertEqual(
            self.remote_other_ssh._git_aggregator_prepare_url(),
            self.remote_other_ssh.url,
            "URL is not prepared correctly",
        )

    def test_git_aggregator_prepare_head(self):
        """Test if head is prepared correctly"""

        # -- 1 --
        # GitHub + PR/MR as link
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "refs/pull/123/head",
            "Head is not prepared correctly",
        )

        # -- 2 --
        # GitHub + PR/MR as number
        self.remote_github_https.write({"head": "123", "head_type": "pr"})
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "refs/pull/123/head",
            "Head is not prepared correctly",
        )

        # -- 3 --
        # GitHub + branch as name
        self.remote_github_https.write({"head": "main", "head_type": "branch"})
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            self.remote_github_https.head,
            "Head is not prepared correctly",
        )

        # -- 4 --
        # GitHub + branch as link
        self.remote_github_https.write(
            {
                "head": "https://github.com/cetmix/cetmix-tower/tree/14.0-demo-branch",
                "head_type": "branch",
            }
        )
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "14.0-demo-branch",
            "Head is not prepared correctly",
        )

        # -- 5 --
        # GitHub + commit as number
        self.remote_github_https.write({"head": "1234567890", "head_type": "commit"})
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "1234567890",
            "Head is not prepared correctly",
        )

        # -- 6 --
        # GitHub + commit as link
        self.remote_github_https.head = (
            "https://github.com/cetmix/cetmix-tower/commit/1234567890"
        )
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "1234567890",
            "Head is not prepared correctly",
        )
