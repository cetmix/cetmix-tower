# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import Mock, patch

from requests.exceptions import Timeout

from odoo.exceptions import AccessError, UserError

from odoo.addons.cetmix_tower_git.tests.common import CommonTest

_REPO_GET = "odoo.addons.cetmix_tower_git_github.models.cx_tower_git_repo.requests.get"


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

    def _repo_api_payload(self, repo_id=1296269, private=False, owner_id=583231):
        """Build a GitHub repository payload for sync tests.

        Args:
            repo_id (int): GitHub repository id.
            private (bool): GitHub ``private`` flag.
            owner_id (int): GitHub owner id.

        Returns:
            dict: Payload accepted by the sync helper.
        """
        return {"id": repo_id, "private": private, "owner": {"id": owner_id}}

    def _mock_repo_get(self, payload, status_code=200):
        """Return a patch context for repository metadata GET.

        Args:
            payload (dict | list | None): JSON body.
            status_code (int): HTTP status.

        Returns:
            unittest.mock._patch: Patch of ``requests.get`` on the repo model.
        """
        response = self._response(status_code, payload)
        return patch(_REPO_GET, return_value=response)

    def test_github_create_stores_ids_and_private(self):
        """A github.com create stores repo id, private, and owner id."""
        key = self.Key.create(
            {"name": "Sync key", "key_type": "s", "secret_value": "ghp_sync"}
        )
        with self._mock_repo_get(self._repo_api_payload(private=True)):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/sync-one.git",
                    "secret_id": key.id,
                }
            )
        self.assertEqual(repo.github_repo_ref, "1296269")
        self.assertTrue(repo.is_private)
        self.assertEqual(repo.owner_id.github_owner_ref, "583231")

    def test_second_repo_keeps_equal_owner_id(self):
        """A second repo of the same owner does not change an equal owner id."""
        key = self.Key.create(
            {"name": "Sync key 2", "key_type": "s", "secret_value": "ghp_sync2"}
        )
        payload = self._repo_api_payload(owner_id=999001)
        with self._mock_repo_get(payload):
            first = self.Repo.create(
                {
                    "url": "https://github.com/octocat/sync-a.git",
                    "secret_id": key.id,
                }
            )
        self.assertEqual(first.owner_id.github_owner_ref, "999001")
        with self._mock_repo_get(payload):
            second = self.Repo.create(
                {
                    "url": "https://github.com/octocat/sync-b.git",
                    "secret_id": key.id,
                }
            )
        self.assertEqual(second.owner_id, first.owner_id)
        self.assertEqual(first.owner_id.github_owner_ref, "999001")

    def test_non_github_create_performs_no_http(self):
        """A non-github.com create performs no GitHub GET."""
        with patch(_REPO_GET, side_effect=AssertionError("http called")):
            repo = self.Repo.create(
                {"url": "https://gitlab.com/octocat/gitlab-only.git"}
            )
        self.assertFalse(repo.github_repo_ref)

    def test_create_without_secret_does_not_call_http(self):
        """A create with no resolvable secret does not call GitHub."""
        with patch(_REPO_GET, side_effect=AssertionError("http called")):
            repo = self.Repo.create({"url": "https://github.com/octocat/no-secret.git"})
        self.assertFalse(repo.github_repo_ref)

    def test_create_failure_clears_github_repo_ref(self):
        """Failed sync on create clears github_repo_ref and does not raise."""
        key = self.Key.create(
            {"name": "Fail key", "key_type": "s", "secret_value": "ghp_fail"}
        )
        with self._mock_repo_get({"message": "x"}, status_code=401):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/bad-401.git",
                    "secret_id": key.id,
                }
            )
        self.assertFalse(repo.github_repo_ref)
        response = self._response(200, None)
        response.json.side_effect = ValueError("not json")
        with patch(_REPO_GET, return_value=response):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/bad-json.git",
                    "secret_id": key.id,
                }
            )
        self.assertFalse(repo.github_repo_ref)
        with self._mock_repo_get([], status_code=200):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/bad-list.git",
                    "secret_id": key.id,
                }
            )
        self.assertFalse(repo.github_repo_ref)
        with self._mock_repo_get({"id": 1, "private": True}, status_code=200):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/bad-payload.git",
                    "secret_id": key.id,
                }
            )
        self.assertFalse(repo.github_repo_ref)
        with patch(_REPO_GET, side_effect=Timeout("timed out")):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/timeout.git",
                    "secret_id": key.id,
                }
            )
        self.assertFalse(repo.github_repo_ref)

    def test_button_failures_raise_user_error(self):
        """Sync failures from the button raise UserError."""
        key = self.Key.create(
            {"name": "Btn key", "key_type": "s", "secret_value": "ghp_btn"}
        )
        repo = self.Repo.create(
            {
                "url": "https://github.com/octocat/button.git",
                "secret_id": key.id,
            }
        )
        with self._mock_repo_get({"message": "Nope"}, status_code=403):
            with self.assertRaises(UserError):
                repo.action_git_github_sync()
        response = self._response(200, None)
        response.json.side_effect = ValueError("not json")
        with patch(_REPO_GET, return_value=response):
            with self.assertRaises(UserError):
                repo.action_git_github_sync()
        with self._mock_repo_get({"id": 1}, status_code=200):
            with self.assertRaises(UserError):
                repo.action_git_github_sync()
        with patch(_REPO_GET, side_effect=Timeout("timed out")):
            with self.assertRaises(UserError):
                repo.action_git_github_sync()
        repo.write({"secret_id": False})
        with patch(_REPO_GET, side_effect=AssertionError("http")):
            with self.assertRaises(UserError):
                repo.action_git_github_sync()

    def test_failed_url_write_clears_repo_ref_keeps_owner_and_private(self):
        """A failing URL change clears repo id and keeps owner id and private."""
        key = self.Key.create(
            {"name": "Url key", "key_type": "s", "secret_value": "ghp_url"}
        )
        with self._mock_repo_get(self._repo_api_payload(private=True, owner_id=42)):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/url-old.git",
                    "secret_id": key.id,
                }
            )
        owner_ref = repo.owner_id.github_owner_ref
        repo.write({"is_private": False})
        with self._mock_repo_get({"message": "fail"}, status_code=502):
            repo.write({"url": "https://github.com/octocat/url-new.git"})
        self.assertFalse(repo.github_repo_ref)
        self.assertEqual(repo.owner_id.github_owner_ref, owner_ref)
        self.assertFalse(repo.is_private)

    def test_non_github_host_write_clears_repo_ref_without_http(self):
        """A write that sets a non-github.com host clears repo id without HTTP."""
        key = self.Key.create(
            {"name": "Host key", "key_type": "s", "secret_value": "ghp_host"}
        )
        with self._mock_repo_get(self._repo_api_payload(owner_id=55)):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/host-switch.git",
                    "secret_id": key.id,
                }
            )
        owner_ref = repo.owner_id.github_owner_ref
        with patch(_REPO_GET, side_effect=AssertionError("http called")):
            repo.write(
                {
                    "url": "https://gitlab.com/octocat/host-switch.git",
                    "provider": "gitlab",
                }
            )
        self.assertFalse(repo.github_repo_ref)
        self.assertEqual(repo.owner_id.github_owner_ref, owner_ref)

    def test_duplicate_url_create_is_not_fetched(self):
        """An existing repo returned for the same URL is not fetched again."""
        key = self.Key.create(
            {"name": "Dup key", "key_type": "s", "secret_value": "ghp_dup"}
        )
        url = "https://github.com/octocat/dup-repo.git"
        with self._mock_repo_get(self._repo_api_payload()) as mock_get:
            first = self.Repo.create({"url": url, "secret_id": key.id})
            count = mock_get.call_count
            second = self.Repo.create({"url": url, "secret_id": key.id})
        self.assertEqual(first, second)
        self.assertEqual(mock_get.call_count, count)

    def test_successful_url_change_performs_one_get(self):
        """One successful URL change performs one GitHub GET."""
        key = self.Key.create(
            {"name": "One get", "key_type": "s", "secret_value": "ghp_one"}
        )
        with self._mock_repo_get(self._repo_api_payload()) as mock_get:
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/one-a.git",
                    "secret_id": key.id,
                }
            )
            mock_get.reset_mock()
            repo.write({"url": "https://github.com/octocat/one-b.git"})
            self.assertEqual(mock_get.call_count, 1)
            mock_get.reset_mock()
            repo.write(
                {
                    "url": "https://github.com/octocat/one-c.git",
                    "repo": "one-c",
                }
            )
        self.assertEqual(mock_get.call_count, 1)

    def test_owner_created_by_another_user_keeps_owner_ref_on_create(self):
        """Create does not raise when the owner was created by another user."""
        manager_b = self.Users.create(
            {
                "name": "Other Manager",
                "login": "other_manager_5709",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.group_manager.id,
                            self.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )
        owner = self.RepoOwner.with_user(self.manager).create(
            {"name": "sharedowner", "github_owner_ref": "100"}
        )
        key = self.Key.create(
            {"name": "Shared key", "key_type": "s", "secret_value": "ghp_shared"}
        )
        with self._mock_repo_get(self._repo_api_payload(owner_id=200)):
            repo = self.Repo.with_user(manager_b).create(
                {
                    "url": "https://github.com/sharedowner/shared.git",
                    "secret_id": key.id,
                }
            )
        self.assertEqual(repo.github_repo_ref, "1296269")
        self.assertEqual(owner.github_owner_ref, "100")

    def test_group_user_cannot_run_sync_action(self):
        """Tower User cannot run the Read from GitHub server action."""
        action = self.env.ref(
            "cetmix_tower_git_github.cx_tower_git_repo_git_github_sync_action"
        )
        with self.assertRaises(AccessError):
            action.with_user(self.user).with_context(
                active_model="cx.tower.git.repo",
                active_ids=self.github_repo.ids,
            ).run()

    def test_wizard_on_owner_clash_overwrite_and_cancel(self):
        """Clash opens a wizard; Cancel keeps owner id; Overwrite replaces it."""
        key = self.Key.create(
            {"name": "Wizard key", "key_type": "s", "secret_value": "ghp_wiz"}
        )
        with self._mock_repo_get(self._repo_api_payload(owner_id=222)):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/wizard.git",
                    "secret_id": key.id,
                }
            )
        repo.owner_id.write({"github_owner_ref": "111"})
        with self._mock_repo_get(self._repo_api_payload(owner_id=222)):
            action = repo.action_git_github_sync()
        self.assertEqual(action["res_model"], "cx.tower.git.github.sync.wizard")
        wizard = self.env["cx.tower.git.github.sync.wizard"].browse(action["res_id"])
        self.assertEqual(repo.github_repo_ref, "1296269")
        self.assertEqual(repo.owner_id.github_owner_ref, "111")
        wizard.action_cancel()
        self.assertEqual(repo.owner_id.github_owner_ref, "111")
        with self._mock_repo_get(self._repo_api_payload(owner_id=333)):
            repo.owner_id.write({"github_owner_ref": "111"})
            action = repo.action_git_github_sync()
        wizard = self.env["cx.tower.git.github.sync.wizard"].browse(action["res_id"])
        wizard.action_overwrite()
        self.assertEqual(repo.owner_id.github_owner_ref, "333")

    def test_overwrite_other_users_owner_raises_access_error(self):
        """Overwrite leaves an owner created by someone else unchanged."""
        manager_b = self.Users.create(
            {
                "name": "Overwrite Manager",
                "login": "overwrite_manager_5709",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.group_manager.id,
                            self.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )
        owner = self.RepoOwner.with_user(self.manager).create(
            {"name": "clashowner", "github_owner_ref": "100"}
        )
        key = self.Key.create(
            {"name": "Clash key", "key_type": "s", "secret_value": "ghp_clash"}
        )
        with self._mock_repo_get(self._repo_api_payload(owner_id=200)):
            repo = self.Repo.with_user(manager_b).create(
                {
                    "url": "https://github.com/clashowner/shared.git",
                    "secret_id": key.id,
                }
            )
        with self._mock_repo_get(self._repo_api_payload(owner_id=200)):
            action = repo.with_user(manager_b).action_git_github_sync()
        wizard = (
            self.env["cx.tower.git.github.sync.wizard"]
            .browse(action["res_id"])
            .with_user(manager_b)
        )
        with self.assertRaises(AccessError):
            wizard.action_overwrite()
        self.assertEqual(owner.github_owner_ref, "100")

    def test_repository_secret_beats_owner_secret(self):
        """A set repository Secret is used and the owner Secret is not."""
        owner_key = self.Key.create(
            {
                "name": "Owner secret",
                "key_type": "s",
                "secret_value": "owner-token",
            }
        )
        repo_key = self.Key.create(
            {
                "name": "Repo secret",
                "key_type": "s",
                "secret_value": "repo-token",
            }
        )
        repo = self.Repo.create({"url": "https://github.com/octocat/beat-owner.git"})
        repo.owner_id.write({"secret_id": owner_key.id})
        with self._mock_repo_get(self._repo_api_payload()) as mock_get:
            repo.write({"secret_id": repo_key.id, "url": repo.url})
        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer repo-token")
        token = self.GitRemote._git_head_api_token(repo)
        self.assertEqual(token, "repo-token")

    def test_empty_repository_secret_uses_owner_secret(self):
        """An empty repository Secret uses the owner Secret for sync."""
        owner_key = self.Key.create(
            {
                "name": "Owner only",
                "key_type": "s",
                "secret_value": "owner-only",
            }
        )
        self.RepoOwner.create({"name": "owneronly", "secret_id": owner_key.id})
        with self._mock_repo_get(self._repo_api_payload()) as mock_get:
            self.Repo.create({"url": "https://github.com/owneronly/owner-only.git"})
        self.assertEqual(
            mock_get.call_args.kwargs["headers"]["Authorization"],
            "Bearer owner-only",
        )

    def test_both_secrets_empty_use_settings_for_sync(self):
        """When both secrets are empty, sync uses the settings key global value."""
        settings_key = self.Key.create(
            {
                "name": "Settings sync",
                "key_type": "s",
                "secret_value": "settings-sync",
            }
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_git_github.default_secret_id",
            str(settings_key.id),
        )
        with self._mock_repo_get(self._repo_api_payload()) as mock_get:
            self.Repo.create({"url": "https://github.com/octocat/settings-sync.git"})
        self.assertEqual(
            mock_get.call_args.kwargs["headers"]["Authorization"],
            "Bearer settings-sync",
        )

    def test_owner_secret_resolves_scopes_for_head_autocomplete(self):
        """Head autocomplete still resolves owner Secret with server and partner."""
        owner_key = self.Key.create(
            {"name": "Owner scope", "key_type": "s", "secret_value": "ignored"}
        )
        partner = self.user_bob.partner_id
        self.KeyValue.create(
            {
                "key_id": owner_key.id,
                "server_id": self.server_test_1.id,
                "partner_id": partner.id,
                "secret_value": "owner-scoped",
            }
        )
        repo = self.Repo.create({"url": "https://github.com/octocat/owner-scope.git"})
        repo.owner_id.write({"secret_id": owner_key.id})
        token = self.GitRemote._git_head_api_token(repo, self.server_test_1, partner)
        self.assertEqual(token, "owner-scoped")

    def test_token_not_in_stored_fields_or_user_error(self):
        """The token is not stored on the repo or shown in UserError text."""
        secret = "ghp_must_not_leak"
        key = self.Key.create(
            {"name": "Leak key", "key_type": "s", "secret_value": secret}
        )
        with self._mock_repo_get(self._repo_api_payload()):
            repo = self.Repo.create(
                {
                    "url": "https://github.com/octocat/leak.git",
                    "secret_id": key.id,
                }
            )
        self.assertNotIn(secret, repo.github_repo_ref or "")
        with self._mock_repo_get({"message": "denied"}, status_code=401):
            with self.assertRaises(UserError) as error:
                repo.action_git_github_sync()
        self.assertNotIn(secret, str(error.exception))
        with self.assertLogs(
            "odoo.addons.cetmix_tower_git_github.models.cx_tower_git_repo",
            level="INFO",
        ) as logs:
            with self._mock_repo_get({"message": "denied"}, status_code=401):
                repo.write({"url": "https://github.com/octocat/leak-log.git"})
        self.assertNotIn(secret, "\n".join(logs.output))
