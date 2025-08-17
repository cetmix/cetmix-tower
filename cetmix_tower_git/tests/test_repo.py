from odoo.exceptions import ValidationError

from .common import CommonTest


class TestRepo(CommonTest):
    """Test class for git repository."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_repo_create_from_url_https_success(self):
        """Test if repository is created correctly"""
        # -- 1 --
        # Valid HTTPS URL
        repo = self.Repo.create(
            {
                "url": "https://github.com/memes-demo/doge-memes.git",
            }
        )
        repo.invalidate_recordset()

        self.assertEqual(repo.name, "github.com/memes-demo/doge-memes")
        self.assertEqual(repo.host, "github.com")
        self.assertEqual(repo.owner_id.name, "memes-demo")
        self.assertEqual(repo.provider, "github")
        self.assertEqual(repo.is_private, False)
        self.assertEqual(repo.url_ssh, "git@github.com:memes-demo/doge-memes.git")
        self.assertEqual(repo.url_git, "git://github.com/memes-demo/doge-memes.git")

    def test_repo_create_from_url_ssh_success(self):
        """Test if repository is created correctly"""
        # -- 1 --
        # Valid SSH URL
        repo = self.Repo.create(
            {
                "url": "git@gitlab.com:chad-guy/chad-guy.git",
            }
        )
        repo.invalidate_recordset()

        self.assertEqual(repo.name, "gitlab.com/chad-guy/chad-guy")
        self.assertEqual(repo.host, "gitlab.com")
        self.assertEqual(repo.owner_id.name, "chad-guy")
        self.assertEqual(repo.provider, "gitlab")
        self.assertEqual(repo.is_private, False)
        self.assertEqual(repo.url, "https://gitlab.com/chad-guy/chad-guy.git")
        self.assertEqual(repo.url_git, "git://gitlab.com/chad-guy/chad-guy.git")

    def test_repo_create_from_url_git_success(self):
        """Test if repository is created correctly"""
        # -- 1 --
        # Valid GIT URL
        repo = self.Repo.create(
            {
                "url": "git://bitbucket.com/much-pepe/pepe-memes.git",
            }
        )
        self.assertEqual(repo.name, "bitbucket.com/much-pepe/pepe-memes")
        self.assertEqual(repo.host, "bitbucket.com")
        self.assertEqual(repo.owner_id.name, "much-pepe")
        self.assertEqual(repo.provider, "bitbucket")
        self.assertEqual(repo.is_private, False)
        self.assertEqual(repo.url_ssh, "git@bitbucket.com:much-pepe/pepe-memes.git")
        self.assertEqual(repo.url, "https://bitbucket.com/much-pepe/pepe-memes.git")

    def test_repo_create_from_url_fails(self):
        """Test if repository creation fails with invalid URLs"""

        # Invalid URL 1
        with self.assertRaises(ValidationError):
            self.Repo.create(
                {
                    "url": "something.com",
                }
            )
        # Invalid URL 2
        with self.assertRaises(ValidationError):
            self.Repo.create(
                {
                    "url": "random string",
                }
            )
