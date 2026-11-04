from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form

from .common import CommonTest


class TestRemote(CommonTest):
    """Test class for git remote."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create another manager for testing
        cls.manager_2 = cls.Users.create(
            {
                "name": "Second Manager",
                "login": "manager2",
                "email": "manager2@test.com",
                "groups_id": [(4, cls.env.ref("cetmix_tower_base.group_manager").id)],
            }
        )

        # Create test project and source as root
        cls.project = cls.GitProject.create(
            {
                "name": "Test Project",
            }
        )
        cls.source = cls.GitSource.create(
            {
                "name": "Test Source",
                "git_project_id": cls.project.id,
            }
        )
        cls.repo_cetmix_tower = cls.Repo.create(
            {
                "name": "Cetmix Tower",
                "url": "https://github.com/cetmix-test/cetmix-tower.git",
            }
        )
        cls.remote = cls.GitRemote.create(
            {
                "repo_id": cls.repo_cetmix_tower.id,
                "source_id": cls.source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        cls.repo_test = cls.Repo.create(
            {
                "name": "Test Repository",
                "url": "https://github.com/cetmix-test/test.git",
            }
        )

    def test_user_access(self):
        """Test that regular users have no access to git remotes"""
        user_remote = self.GitRemote.with_user(self.user)

        # Test CRUD operations
        with self.assertRaises(AccessError):
            user_remote.create(
                {
                    "repo_id": self.repo_test.id,
                    "url_protocol": "https",
                    "source_id": self.source.id,
                    "head": "main",
                }
            )
        self.assertFalse(user_remote.search([("id", "=", self.remote.id)]))
        with self.assertRaises(AccessError):
            self.remote.with_user(self.user).write({"head": "dev"})
        with self.assertRaises(AccessError):
            self.remote.with_user(self.user).unlink()

    def test_manager_read_access(self):
        """Test manager read access rules"""
        manager_remote = self.GitRemote.with_user(self.manager)

        # Manager not in project user_ids or manager_ids - should not read
        self.assertFalse(manager_remote.search([("id", "=", self.remote.id)]))

        # Add manager to project user_ids - should read
        self.project.write({"user_ids": [(4, self.manager.id)]})
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")

        # Remove from user_ids, add to manager_ids - should read
        self.project.write(
            {"user_ids": [(3, self.manager.id)], "manager_ids": [(4, self.manager.id)]}
        )
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote.exists())

    def test_manager_write_access(self):
        """Test manager write/create access rules"""
        manager_remote = self.GitRemote.with_user(self.manager)

        # Create project as manager - should be added to manager_ids automatically
        project = self.GitProject.with_user(self.manager).create(
            {
                "name": "Manager Project",
            }
        )
        source = self.GitSource.with_user(self.manager).create(
            {
                "name": "Manager Source",
                "git_project_id": project.id,
            }
        )

        # Create remote in own project - should succeed
        new_remote = manager_remote.create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        self.assertTrue(new_remote.exists())

        # Write to own remote - should succeed
        new_remote.write({"head": "dev"})
        self.assertEqual(new_remote.head, "dev")

        # Write to other's remote - should fail
        with self.assertRaises(AccessError):
            self.remote.with_user(self.manager).write({"head": "dev"})

    def test_manager_unlink_access(self):
        """Test manager unlink access rules"""
        # Create project and remote as manager_2
        project = self.GitProject.with_user(self.manager_2).create(
            {
                "name": "Manager 2 Project",
            }
        )
        source = self.GitSource.create(
            {
                "name": "Manager 2 Source",
                "git_project_id": project.id,
            }
        )
        remote = self.GitRemote.with_user(self.manager_2).create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )

        # Try delete as different manager - should fail even if added to manager_ids
        project.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            remote.with_user(self.manager).unlink()

        # Create remote as manager and try delete - should succeed
        own_remote = self.GitRemote.with_user(self.manager).create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        self.assertTrue(own_remote.exists())
        own_remote.with_user(self.manager).unlink()
        self.assertFalse(own_remote.exists())

    def test_root_access(self):
        """Test root access rules"""
        root_remote = self.GitRemote.with_user(self.root)

        # Create
        new_remote = root_remote.create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": self.source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        self.assertTrue(new_remote.exists())

        # Read
        remote = root_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")

        # Write
        self.remote.with_user(self.root).write({"head": "dev"})
        self.assertEqual(self.remote.head, "dev")

        # Delete
        new_remote.with_user(self.root).unlink()
        self.assertFalse(new_remote.exists())

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
            "gitlab",  # this is how giturlparse detects the provider
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

    def test_git_aggregator_prepare_url(self):
        """Test if url is prepared correctly"""

        # -- 1 --
        # GitHub + https
        self.remote_github_https.repo_id.is_private = False
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_url(),
            self.remote_github_https.repo_id.url,
            "URL is not prepared correctly",
        )

        # -- 2 --
        # GitHub + https -> private
        self.remote_github_https.repo_id.is_private = True
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_url(),
            "https://$GITHUB_TOKEN:x-oauth-basic@github.com/cetmix-test/cetmix-tower-test.git",
            "URL is not prepared correctly",
        )

        # -- 3 --
        # Gitlab + https
        self.remote_gitlab_https.repo_id.is_private = False
        self.assertEqual(
            self.remote_gitlab_https._git_aggregator_prepare_url(),
            self.remote_gitlab_https.repo_id.url,
            "URL is not prepared correctly",
        )

        # -- 4 --
        # Gitlab + https -> private
        self.remote_gitlab_https.repo_id.is_private = True
        self.assertEqual(
            self.remote_gitlab_https._git_aggregator_prepare_url(),
            "https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@my.gitlab.com/cetmix-test/cetmix-tower-test.git",
            "URL is not prepared correctly",
        )

        # -- 5 --
        # Bitbucket + https
        self.remote_bitbucket_https.repo_id.is_private = False
        self.assertEqual(
            self.remote_bitbucket_https._git_aggregator_prepare_url(),
            self.remote_bitbucket_https.repo_id.url,
            "URL is not prepared correctly",
        )

        # -- 6 --
        # Bitbucket + https -> private
        self.remote_bitbucket_https.repo_id.is_private = True
        self.assertEqual(
            self.remote_bitbucket_https._git_aggregator_prepare_url(),
            "https://x-token-auth:$BITBUCKET_TOKEN@bitbucket.com/cetmix-test/cetmix-tower-test-enterprise.git",
            "URL is not prepared correctly",
        )

        # -- 7 --
        # Other + ssh
        self.remote_other_ssh.repo_id.is_private = False
        self.assertEqual(
            self.remote_other_ssh._git_aggregator_prepare_url(),
            self.remote_other_ssh.repo_id.url_ssh,
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
                "head": "https://github.com/cetmix-test/cetmix-tower/list/14.0-demo-branch",
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
            "https://github.com/cetmix-test/cetmix-tower/commit/1234567890"
        )
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "1234567890",
            "Head is not prepared correctly",
        )

    def _github_repo(self, secret=None, private=False):
        """Create a github.com repository with a unique name.

        Args:
            secret (cx.tower.key | None): Repository Secret.
            private (bool): Private flag.

        Returns:
            cx.tower.git.repo: Created repository.
        """
        suffix = self.env["cx.tower.git.repo"].search_count([])
        repo = self.Repo.create(
            {
                "url": f"https://github.com/cetmix-test/head-auto-{suffix}.git",
                "is_private": private,
            }
        )
        if secret:
            repo.secret_id = secret
        return repo

    def _api_key(self, name, global_value, values=None):
        """Create a secret and optional server or partner values.

        Args:
            name (str): Key name.
            global_value (str | None): Global secret value. Skipped when
                empty.
            values (list[dict] | None): Extra ``cx.tower.key.value`` dicts
                without ``key_id``.

        Returns:
            cx.tower.key: Created key.
        """
        vals = {"name": name, "key_type": "s"}
        if global_value:
            vals["secret_value"] = global_value
        key = self.Key.create(vals)
        for value in values or []:
            self.KeyValue.create(dict(value, key_id=key.id))
        return key

    def _autocomplete(self, repo, user=None, query=False, **context):
        """Call Head autocomplete with a GitHub hook that records the token.

        Args:
            repo (cx.tower.git.repo | None): Repository, or ``None`` when
                the context must not name one.
            user (res.users | None): User for the call. Defaults to superuser.
            query (str | bool): Value passed to the method.
            **context: Extra field context.

        Returns:
            dict: ``rows``, ``server``, ``partner``, and ``token`` when the
            hook ran.
        """
        captured = {}

        def _hook(
            records,
            fetched_repo,
            head_type,
            fetched_query,
            server=None,
            partner=None,
        ):
            captured["server"] = server
            captured["partner"] = partner
            captured["head_type"] = head_type
            captured["query"] = fetched_query
            captured["token"] = records._git_head_api_token(
                fetched_repo, server, partner
            )
            return [{"head": "listed"}]

        ctx = {"git_head_type": "branch"}
        if repo:
            ctx["git_repo_id"] = repo.id
        ctx.update(context)
        remotes = self.GitRemote
        if user:
            remotes = remotes.with_user(user)
        with patch.object(
            type(self.GitRemote),
            "_git_fetch_heads_github",
            _hook,
            create=True,
        ):
            captured["rows"] = remotes.with_context(**ctx).git_head_autocomplete(query)
        return captured

    def test_head_slash_is_stored_whole(self):
        """A branch name that contains a slash is not reduced to its tail."""
        remote = self.GitRemote.create(
            {
                "repo_id": self.repo_test.id,
                "source_id": self.source.id,
                "head_type": "branch",
                "head": "  feat/2233  ",
            }
        )
        self.assertEqual(remote.head, "feat/2233")
        self.assertEqual(remote._git_aggregator_prepare_head(), "feat/2233")

        remote.write({"head": "release/18.0"})
        self.assertEqual(remote.head, "release/18.0")
        self.assertEqual(remote._git_aggregator_prepare_head(), "release/18.0")

    def test_head_reference_is_stored_instead_of_caption(self):
        """A selected reference replaces the visible suggestion."""
        full_sha = "6e427eb" + ("a" * 33)
        remote = self.GitRemote.create(
            {
                "repo_id": self.repo_test.id,
                "source_id": self.source.id,
                "head_type": "commit",
                "head": "6e427eb subject line",
                "head_reference": full_sha,
            }
        )
        self.assertEqual(remote.head, full_sha)
        self.assertFalse(remote.head_reference)
        self.assertEqual(remote._git_aggregator_prepare_head(), full_sha)
        remote.write(
            {
                "head": "6e427eb another subject",
                "head_reference": full_sha,
            }
        )
        self.assertEqual(remote.head, full_sha)
        chosen = self.GitRemote.new(
            {
                "repo_id": self.repo_test.id,
                "source_id": self.source.id,
                "head_type": "commit",
                "head": "6e427eb subject line",
                "head_reference": full_sha,
            }
        )
        chosen.onchange_head()
        self.assertEqual(chosen.head, full_sha)
        self.assertFalse(chosen.head_reference)
        with Form(remote) as remote_form:
            remote_form.head = "main"
        self.assertEqual(remote.head, "main")
        self.assertEqual(remote._git_aggregator_prepare_head(), "main")

    def test_https_head_keeps_last_segment(self):
        """A pasted link is still the last path segment."""
        self.remote.write(
            {
                "head": "https://github.com/cetmix-test/cetmix-tower/tree/14.0-demo-branch",
                "head_type": "branch",
            }
        )
        self.assertEqual(self.remote.head, "14.0-demo-branch")
        self.assertEqual(self.remote._git_aggregator_prepare_head(), "14.0-demo-branch")

    def test_autocomplete_without_repo_or_hook(self):
        """A missing repository or a provider without a hook returns no rows."""
        self.assertEqual(
            self.GitRemote.with_context(git_head_type="branch").git_head_autocomplete(
                False
            ),
            [],
        )
        rows = self.GitRemote.with_context(
            git_repo_id=self.repo_gitlab_private.id,
            git_head_type="branch",
        ).git_head_autocomplete(False)
        self.assertEqual(rows, [])

    def test_user_cannot_autocomplete(self):
        """A user without write access on Git remotes cannot list heads."""
        with self.assertRaises(AccessError):
            self.GitRemote.with_user(self.user).git_head_autocomplete(False)

    def test_source_with_one_jet_uses_jet_server_and_partner(self):
        """The remote form uses the single Jet of the source's project."""
        partner = self.user_bob.partner_id
        self.server_test_1.partner_id = partner
        self.Jet.create(
            {
                "name": "Single Head Jet",
                "jet_template_id": self.jet_template_sample.id,
                "server_id": self.server_test_1.id,
                "partner_id": partner.id,
                "git_project_id": self.project.id,
            }
        )
        key = self._api_key(
            "Jet secret",
            "global-token",
            [
                {
                    "secret_value": "jet-token",
                    "server_id": self.server_test_1.id,
                    "partner_id": partner.id,
                }
            ],
        )
        captured = self._autocomplete(
            self._github_repo(key, private=True),
            git_source_id=self.source.id,
        )
        self.assertEqual(captured["server"], self.server_test_1)
        self.assertEqual(captured["partner"], partner)
        self.assertEqual(captured["token"], "jet-token")

    def test_source_without_jet_uses_linked_server(self):
        """No Jet and one linked server uses that server and its partner."""
        partner = self.user_bob.partner_id
        self.server_test_1.partner_id = partner
        server_file = self.File.create(
            {
                "name": "head-autocomplete.yml",
                "server_id": self.server_test_1.id,
            }
        )
        self.GitProjectRel.create(
            {
                "git_project_id": self.project.id,
                "server_id": self.server_test_1.id,
                "file_id": server_file.id,
                "project_format": "git_aggregator",
            }
        )
        key = self._api_key(
            "Linked server secret",
            "global-token",
            [
                {
                    "secret_value": "linked-token",
                    "server_id": self.server_test_1.id,
                    "partner_id": partner.id,
                }
            ],
        )
        captured = self._autocomplete(
            self._github_repo(key, private=True),
            git_source_id=self.source.id,
        )
        self.assertEqual(captured["server"], self.server_test_1)
        self.assertEqual(captured["partner"], partner)
        self.assertEqual(captured["token"], "linked-token")

    def test_partner_is_ignored_when_no_readable_jet_matches(self):
        """A partner is used only when a readable Jet on that server has it."""
        partner = self.user_bob.partner_id
        other = self.manager.partner_id
        self.server_test_1.write(
            {
                "user_ids": [(4, self.manager.id)],
                "manager_ids": [(4, self.manager.id)],
            }
        )
        self.Jet.create(
            {
                "name": "Hidden partner jet",
                "jet_template_id": self.jet_template_sample.id,
                "server_id": self.server_test_1.id,
                "partner_id": partner.id,
            }
        )
        key = self._api_key(
            "Partner secret",
            "global-token",
            [
                {
                    "secret_value": "server-token",
                    "server_id": self.server_test_1.id,
                },
                {
                    "secret_value": "both-token",
                    "server_id": self.server_test_1.id,
                    "partner_id": partner.id,
                },
            ],
        )
        repo = self._github_repo(key, private=True)
        mismatched = self._autocomplete(
            repo,
            git_server_id=self.server_test_1.id,
            git_partner_id=other.id,
        )
        self.assertEqual(mismatched["token"], "server-token")
        hidden = self._autocomplete(
            repo,
            user=self.manager,
            git_server_id=self.server_test_1.id,
            git_partner_id=partner.id,
        )
        self.assertFalse(hidden["partner"])
        self.assertEqual(hidden["token"], "server-token")

    def test_non_numeric_context_id_is_ignored(self):
        """A context id that is not a number selects no repository."""
        rows = self.GitRemote.with_context(
            git_repo_id="abc",
            git_head_type="branch",
        ).git_head_autocomplete(False)
        self.assertEqual(rows, [])

    def test_non_numeric_partner_id_is_ignored(self):
        """A partner id that is not a number does not select the partner secret."""
        partner = self.user_bob.partner_id
        key = self._api_key(
            "Partner id secret",
            "global-token",
            [
                {
                    "secret_value": "server-token",
                    "server_id": self.server_test_1.id,
                },
                {
                    "secret_value": "both-token",
                    "server_id": self.server_test_1.id,
                    "partner_id": partner.id,
                },
            ],
        )
        captured = self._autocomplete(
            self._github_repo(key, private=True),
            git_server_id=self.server_test_1.id,
            git_partner_id="abc",
        )
        self.assertFalse(captured["partner"])
        self.assertEqual(captured["token"], "server-token")

    def test_several_jets_use_no_server(self):
        """Several Jets on the project do not select a server secret."""
        for name in ("Head Jet A", "Head Jet B"):
            self.Jet.create(
                {
                    "name": name,
                    "jet_template_id": self.jet_template_sample.id,
                    "server_id": self.server_test_1.id,
                    "git_project_id": self.project.id,
                }
            )
        key = self._api_key(
            "Several jets secret",
            "global-token",
            [
                {
                    "secret_value": "server-token",
                    "server_id": self.server_test_1.id,
                }
            ],
        )
        captured = self._autocomplete(
            self._github_repo(key, private=True),
            git_source_id=self.source.id,
        )
        self.assertFalse(captured["server"])
        self.assertEqual(captured["token"], "global-token")

    def test_several_linked_servers_use_no_server(self):
        """Several linked servers do not select a server secret."""
        other = self.Server.create(
            {
                "name": "Second Head Server",
                "ip_v4_address": "10.9.9.8",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "second",
                "os_id": self.os_debian_10.id,
            }
        )
        for server in (self.server_test_1, other):
            server_file = self.File.create(
                {
                    "name": f"head-{server.id}.yml",
                    "server_id": server.id,
                }
            )
            self.GitProjectRel.create(
                {
                    "git_project_id": self.project.id,
                    "server_id": server.id,
                    "file_id": server_file.id,
                    "project_format": "git_aggregator",
                }
            )
        key = self._api_key(
            "Several servers secret",
            "global-token",
            [
                {
                    "secret_value": "server-token",
                    "server_id": self.server_test_1.id,
                }
            ],
        )
        captured = self._autocomplete(
            self._github_repo(key, private=True),
            git_source_id=self.source.id,
        )
        self.assertFalse(captured["server"])
        self.assertEqual(captured["token"], "global-token")

    def test_unreadable_server_is_ignored(self):
        """A server id the user cannot read does not select that server's secret."""
        hidden = self.Server.create(
            {
                "name": "Hidden Head Server",
                "ip_v4_address": "10.9.9.9",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "hidden",
                "os_id": self.os_debian_10.id,
            }
        )
        key = self._api_key(
            "Hidden server secret",
            "global-token",
            [
                {
                    "secret_value": "hidden-token",
                    "server_id": hidden.id,
                }
            ],
        )
        captured = self._autocomplete(
            self._github_repo(key, private=True),
            user=self.manager,
            git_server_id=hidden.id,
        )
        self.assertFalse(captured["server"])
        self.assertEqual(captured["token"], "global-token")

    def test_public_repository_token(self):
        """A public repository sends a resolved token and errors when none exists."""
        key = self._api_key("Public secret", "public-token")
        captured = self._autocomplete(self._github_repo(key, private=False))
        self.assertEqual(captured["token"], "public-token")

        bare = self._github_repo(private=False)
        with self.assertRaises(UserError):
            self._autocomplete(bare)

    def test_private_repository_without_secret_errors(self):
        """A private repository with no secret errors."""
        with self.assertRaises(UserError):
            self._autocomplete(self._github_repo(private=True))

    def test_manager_server_based_access(self):
        """Test manager access to remotes through server relationships"""
        manager_remote = self.GitRemote.with_user(self.manager)

        # Create a server where manager is a user
        server = self.Server.create(
            {
                "name": "Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
                "user_ids": [(4, self.manager.id)],
            }
        )

        # Link project to server
        file = self.File.create(
            {
                "name": "test_file",
                "server_id": server.id,
            }
        )
        self.GitProjectRel.create(
            {
                "server_id": server.id,
                "file_id": file.id,
                "git_project_id": self.project.id,
                "project_format": "git_aggregator",
            }
        )

        # Manager should be able to read remote through server relationship
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")

        # Remove manager from server users
        server.write({"user_ids": [(3, self.manager.id)]})

        # Manager should not be able to read remote anymore
        self.assertFalse(manager_remote.search([("id", "=", self.remote.id)]))

        # Add manager to server managers
        server.write({"manager_ids": [(4, self.manager.id)]})

        # Manager should be able to read remote again
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")
