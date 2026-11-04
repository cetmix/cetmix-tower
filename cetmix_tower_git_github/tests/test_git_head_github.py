# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import Mock, patch

from requests.exceptions import Timeout

from odoo.exceptions import UserError

from odoo.addons.cetmix_tower_git.tests.common import CommonTest


class TestGitHeadGithub(CommonTest):
    """GitHub head suggestions. ``requests.get`` is mocked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.github_repo = cls.Repo.create(
            {"url": "https://github.com/octocat/Hello-World.git"}
        )
        cls.api_key = cls.Key.create(
            {
                "name": "GitHub API test",
                "key_type": "s",
                "secret_value": "ghp_test_token",
            }
        )
        cls.github_repo.secret_id = cls.api_key
        cls.enterprise_host = cls.Repo.create(
            {"url": "https://gitlab.com/octocat/Hello-World.git"}
        )
        cls.enterprise_host.write({"provider": "github", "secret_id": cls.api_key.id})

    def _response(self, status_code, payload, reason=""):
        """Build a mocked ``requests`` response.

        Args:
            status_code (int): HTTP status.
            payload (list | dict): JSON body.
            reason (str): HTTP reason.

        Returns:
            Mock: Response whose ``json`` returns ``payload``.
        """
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        response.reason = reason
        return response

    def _fetch(self, repo, head_type, query, payload, status_code=200):
        """Call the GitHub hook with ``requests.get`` mocked.

        Args:
            repo (cx.tower.git.repo): Repository.
            head_type (str): ``branch``, ``pr``, or ``commit``.
            query (str | bool): Typed text, or ``False``.
            payload (list | dict): JSON body.
            status_code (int): HTTP status.

        Returns:
            tuple: ``(rows, mock_get)``.
        """
        response = self._response(status_code, payload, reason="Forbidden")
        with patch(
            "odoo.addons.cetmix_tower_git_github.models.cx_tower_git_remote.requests.get",
            return_value=response,
        ) as mock_get:
            rows = self.GitRemote._git_fetch_heads_github(
                repo, head_type, query, server=None, partner=None
            )
        return rows, mock_get

    def test_branch_pr_and_commit_rows(self):
        """Each head type uses the field git-aggregator can store."""
        branches, mock_get = self._fetch(
            self.github_repo,
            "branch",
            False,
            [{"name": "18.0"}, {"name": "feat/2233"}],
        )
        self.assertEqual(branches, [{"head": "18.0"}, {"head": "feat/2233"}])
        self.assertEqual(mock_get.call_count, 1)
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["page"], 1)
        self.assertEqual(params["per_page"], 100)
        self.assertIn("/repos/octocat/Hello-World/branches", mock_get.call_args.args[0])

        pulls, mock_get = self._fetch(
            self.github_repo,
            "pr",
            False,
            [{"number": 12}, {"number": 3}],
        )
        self.assertEqual(pulls, [{"head": "12"}, {"head": "3"}])
        self.assertEqual(mock_get.call_args.kwargs["params"]["state"], "open")

        commits, mock_get = self._fetch(
            self.github_repo,
            "commit",
            "abc",
            [{"sha": "abc111"}, {"sha": "def222"}],
        )
        self.assertEqual(commits, [{"head": "abc111"}])
        self.assertNotIn("sha", mock_get.call_args.kwargs["params"])

    def test_pr_and_commit_rows_include_caption(self):
        """A pull request shows its title, and a commit shows a short subject."""
        pulls, _mock_get = self._fetch(
            self.github_repo,
            "pr",
            False,
            [
                {
                    "number": 510,
                    "title": "[18.0][ADD] cetmix_tower_git_github: add module",
                }
            ],
        )
        self.assertEqual(
            pulls,
            [{"head": "510 [18.0][ADD] cetmix_tower_git_github: add module"}],
        )
        full_sha = "6e427eb" + ("a" * 33)
        commits, _mock_get = self._fetch(
            self.github_repo,
            "commit",
            False,
            [
                {
                    "sha": full_sha,
                    "commit": {
                        "message": (
                            "[IMP] cetmix_tower_git: autocomplete git heads\n\nbody"
                        )
                    },
                }
            ],
        )
        self.assertEqual(len(full_sha), 40)
        self.assertEqual(
            commits,
            [
                {
                    "head": "6e427eb [IMP] cetmix_tower_git: autocomplete git heads",
                    "head_reference": full_sha,
                }
            ],
        )
        self.assertNotIn("body", commits[0]["head"])
        bare, _mock_get = self._fetch(
            self.github_repo,
            "commit",
            False,
            [{"sha": full_sha, "commit": {"message": ""}}],
        )
        self.assertEqual(bare, [{"head": "6e427eb", "head_reference": full_sha}])

    def test_query_matches_caption_and_full_sha(self):
        """The typed text matches the caption, the number, and the full SHA."""
        pulls, _mock_get = self._fetch(
            self.github_repo,
            "pr",
            "ADD",
            [
                {"number": 510, "title": "[ADD] module"},
                {"number": 509, "title": "other"},
            ],
        )
        self.assertEqual(pulls, [{"head": "510 [ADD] module"}])
        by_number, _mock_get = self._fetch(
            self.github_repo,
            "pr",
            "510",
            [{"number": 510, "title": "[ADD] module"}],
        )
        self.assertEqual(by_number, [{"head": "510 [ADD] module"}])
        full_sha = "6e427eb" + ("b" * 33)
        payload = [
            {
                "sha": full_sha,
                "commit": {"message": "[IMP] autocomplete"},
            }
        ]
        for query in ("6e427eb", "autocomplete", full_sha):
            commits, _mock_get = self._fetch(self.github_repo, "commit", query, payload)
            self.assertEqual(
                commits,
                [
                    {
                        "head": "6e427eb [IMP] autocomplete",
                        "head_reference": full_sha,
                    }
                ],
            )

    def test_caption_is_stored_as_aggregator_value(self):
        """Create and write keep the number or the short commit id."""
        remote = self.GitRemote.create(
            {
                "repo_id": self.github_repo.id,
                "source_id": self.git_source_1.id,
                "head_type": "pr",
                "head": "510 [18.0][ADD] cetmix_tower_git_github: add module",
            }
        )
        self.assertEqual(remote.head, "510")
        self.assertEqual(remote._git_aggregator_prepare_head(), "refs/pull/510/head")
        remote.write({"head": "511 [FIX] feat/2233"})
        self.assertEqual(remote.head, "511")
        self.assertEqual(remote._git_aggregator_prepare_head(), "refs/pull/511/head")
        remote.write(
            {
                "head_type": "commit",
                "head": "6e427eb [IMP] cetmix_tower_git: autocomplete git heads",
            }
        )
        self.assertEqual(remote.head, "6e427eb")
        self.assertEqual(remote._git_aggregator_prepare_head(), "6e427eb")
        full_sha = "6e427eb" + ("c" * 33)
        stored = self.GitRemote.create(
            {
                "repo_id": self.github_repo.id,
                "source_id": self.git_source_1.id,
                "head_type": "commit",
                "head": "6e427eb [IMP] subject",
                "head_reference": full_sha,
            }
        )
        self.assertEqual(stored.head, full_sha)
        self.assertEqual(stored._git_aggregator_prepare_head(), full_sha)
        stored.write({"head": full_sha})
        self.assertEqual(stored.head, full_sha)
        stored.write({"head": f"{full_sha} [IMP] subject"})
        self.assertEqual(stored.head, full_sha)
        self.assertEqual(stored._git_aggregator_prepare_head(), full_sha)
        chosen = self.GitRemote.new({"head_type": "commit", "head": full_sha})
        chosen.onchange_head()
        self.assertEqual(chosen.head, full_sha)
        draft = self.GitRemote.new(
            {
                "repo_id": self.github_repo.id,
                "source_id": self.git_source_1.id,
                "head_type": "pr",
                "head": "512 [ADD] module",
            }
        )
        draft.onchange_head()
        self.assertEqual(draft.head, "512")

    def test_create_caption_uses_default_head_type(self):
        """A context default Head Type is used when create omits the field."""
        remote = self.GitRemote.with_context(default_head_type="pr").create(
            {
                "repo_id": self.github_repo.id,
                "source_id": self.git_source_1.id,
                "head": "510 Fix deployment",
            }
        )
        self.assertEqual(remote.head_type, "pr")
        self.assertEqual(remote.head, "510")
        self.assertEqual(remote._git_aggregator_prepare_head(), "refs/pull/510/head")
        explicit = self.GitRemote.with_context(default_head_type="pr").create(
            {
                "repo_id": self.github_repo.id,
                "source_id": self.git_source_1.id,
                "head_type": "branch",
                "head": "510 Fix deployment",
            }
        )
        self.assertEqual(explicit.head, "510 Fix deployment")

    def test_url_inside_caption_keeps_selected_identifier(self):
        """A URL in the title is not treated as a pasted link."""
        remote = self.GitRemote.create(
            {
                "repo_id": self.github_repo.id,
                "source_id": self.git_source_1.id,
                "head_type": "pr",
                "head": "510 [ADD] see https://github.com/OCA/web/pull/99",
            }
        )
        self.assertEqual(remote.head, "510")
        self.assertEqual(remote._git_aggregator_prepare_head(), "refs/pull/510/head")
        remote.write(
            {
                "head_type": "commit",
                "head": "6e427eb [IMP] see https://example.com/commit/abcdef1",
            }
        )
        self.assertEqual(remote.head, "6e427eb")
        self.assertEqual(remote._git_aggregator_prepare_head(), "6e427eb")
        draft = self.GitRemote.new(
            {
                "head_type": "pr",
                "head": "15 [FIX] docs at https://github.com/OCA/web",
            }
        )
        draft.onchange_head()
        self.assertEqual(draft.head, "15")

    def test_query_keeps_github_order(self):
        """A typed string keeps matching rows in the page order."""
        rows, mock_get = self._fetch(
            self.github_repo,
            "branch",
            "feat",
            [{"name": "main"}, {"name": "Feat/2233"}, {"name": "feature"}],
        )
        self.assertEqual(rows, [{"head": "Feat/2233"}, {"head": "feature"}])
        self.assertEqual(mock_get.call_count, 1)

    def test_request_sends_bearer_token(self):
        """The call is authenticated, and the token is not a suggestion."""
        rows, mock_get = self._fetch(
            self.github_repo, "branch", False, [{"name": "main"}]
        )
        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer ghp_test_token")
        self.assertEqual(headers["Accept"], "application/vnd.github+json")
        self.assertEqual(headers["X-GitHub-Api-Version"], "2026-03-10")
        self.assertEqual(mock_get.call_args.kwargs["timeout"], 10)
        self.assertNotIn("ghp_test_token", str(rows))

    def test_other_host_makes_no_call(self):
        """A GitHub provider on another host does not resolve a token or call."""
        with (
            patch.object(
                type(self.GitRemote),
                "_git_head_api_token",
                side_effect=AssertionError("token resolved"),
            ),
            patch(
                "odoo.addons.cetmix_tower_git_github.models"
                ".cx_tower_git_remote.requests.get",
                side_effect=AssertionError("http called"),
            ),
        ):
            rows = self.GitRemote._git_fetch_heads_github(
                self.enterprise_host, "branch", False
            )
        self.assertEqual(rows, [])
        self.assertNotEqual(self.enterprise_host.host, "github.com")
        self.assertEqual(self.enterprise_host.provider, "github")

    def test_non_200_raises(self):
        """A failed GitHub response raises the response message."""
        with self.assertRaises(UserError) as error:
            self._fetch(
                self.github_repo,
                "branch",
                False,
                {"message": "Bad credentials"},
                status_code=401,
            )
        self.assertIn("Bad credentials", str(error.exception))

    def test_non_list_payload_raises(self):
        """A 200 body that is not a list raises UserError."""
        with self.assertRaises(UserError) as error:
            self._fetch(self.github_repo, "branch", False, {"message": "ok"})
        self.assertIn("unexpected response", str(error.exception))

    def test_missing_owner_makes_no_http_call(self):
        """No owner or repository name returns no rows and does not call GitHub."""
        self.github_repo.write({"owner_id": False, "repo": False})
        with patch(
            "odoo.addons.cetmix_tower_git_github.models"
            ".cx_tower_git_remote.requests.get",
            side_effect=AssertionError("http called"),
        ):
            rows = self.GitRemote._git_fetch_heads_github(
                self.github_repo, "branch", False
            )
        self.assertEqual(rows, [])

    def test_unknown_head_type_makes_no_http_call(self):
        """An unknown head type returns no rows and does not call GitHub."""
        with patch(
            "odoo.addons.cetmix_tower_git_github.models"
            ".cx_tower_git_remote.requests.get",
            side_effect=AssertionError("http called"),
        ):
            rows = self.GitRemote._git_fetch_heads_github(
                self.github_repo, "tag", False
            )
        self.assertEqual(rows, [])

    def test_error_without_message_uses_fallback(self):
        """A non-200 body without a message uses the fallback text."""
        response = self._response(502, None, reason="")
        response.json.side_effect = ValueError("not json")
        with patch(
            "odoo.addons.cetmix_tower_git_github.models.cx_tower_git_remote.requests.get",
            return_value=response,
        ):
            with self.assertRaises(UserError) as error:
                self.GitRemote._git_fetch_heads_github(
                    self.github_repo, "branch", False
                )
        self.assertEqual(str(error.exception), "GitHub returned an error.")

    def test_transport_error_raises_user_error(self):
        """A failed connection raises UserError and keeps the original cause."""
        with patch(
            "odoo.addons.cetmix_tower_git_github.models.cx_tower_git_remote.requests.get",
            side_effect=Timeout("timed out"),
        ):
            with self.assertRaises(UserError) as error:
                self.GitRemote._git_fetch_heads_github(
                    self.github_repo, "branch", False
                )
        self.assertEqual(str(error.exception), "GitHub could not be reached.")
        self.assertIsInstance(error.exception.__cause__, Timeout)

    def test_invalid_json_raises_user_error(self):
        """A HTTP 200 body that is not JSON raises UserError."""
        response = self._response(200, None)
        response.json.side_effect = ValueError("not json")
        with patch(
            "odoo.addons.cetmix_tower_git_github.models.cx_tower_git_remote.requests.get",
            return_value=response,
        ):
            with self.assertRaises(UserError) as error:
                self.GitRemote._git_fetch_heads_github(
                    self.github_repo, "branch", False
                )
        self.assertEqual(
            str(error.exception), "GitHub returned an unexpected response."
        )
        self.assertIsInstance(error.exception.__cause__, ValueError)

    def test_repository_secret_beats_settings_key(self):
        """A repository Secret is used, and the settings key is not."""
        settings_key = self.Key.create(
            {
                "name": "Settings secret",
                "key_type": "s",
                "secret_value": "settings-token",
            }
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_git_github.default_secret_id",
            str(settings_key.id),
        )
        token = self.GitRemote._git_head_api_token(self.github_repo)
        self.assertEqual(token, "ghp_test_token")

    def test_empty_secret_uses_settings_key(self):
        """An empty Secret resolves the settings key for the checked scope."""
        repo = self.Repo.create(
            {"url": "https://github.com/octocat/settings-scope.git"}
        )
        partner = self.user_bob.partner_id
        key = self.Key.create(
            {
                "name": "Settings scope",
                "key_type": "s",
                "secret_value": "settings-global",
            }
        )
        self.KeyValue.create(
            {
                "key_id": key.id,
                "server_id": self.server_test_1.id,
                "partner_id": partner.id,
                "secret_value": "settings-scoped",
            }
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_git_github.default_secret_id",
            str(key.id),
        )
        token = self.GitRemote._git_head_api_token(repo, self.server_test_1, partner)
        self.assertEqual(token, "settings-scoped")

    def test_settings_value_must_be_a_secret_key_id(self):
        """The settings value is used only when it is the id of a secret key."""
        repo = self.Repo.create({"url": "https://github.com/octocat/settings-bad.git"})
        parameter = self.env["ir.config_parameter"].sudo()
        parameter.set_param("cetmix_tower_git_github.default_secret_id", "abc")
        with self.assertRaises(UserError):
            self.GitRemote._git_head_api_token(repo)
        ssh_key = self.Key.create(
            {"name": "SSH not secret", "key_type": "k", "secret_value": "ssh key"}
        )
        parameter.set_param(
            "cetmix_tower_git_github.default_secret_id",
            str(ssh_key.id),
        )
        with self.assertRaises(UserError):
            self.GitRemote._git_head_api_token(repo)
