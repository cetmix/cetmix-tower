# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from numbers import Integral

import requests
from requests.exceptions import RequestException

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .cx_tower_git_remote import GITHUB_API_VERSION

_logger = logging.getLogger(__name__)


class CxTowerGitRepo(models.Model):
    """GitHub repository id and sync for github.com repositories."""

    _inherit = "cx.tower.git.repo"

    github_repo_ref = fields.Char(
        help="GitHub repository id returned by GitHub. Not shown in the UI.",
    )
    secret_id = fields.Many2one(
        help="When empty, the owner Secret is used, then the GitHub API Secret.",
    )

    _SYNC_WRITE_FIELDS = frozenset({"url", "host", "owner_id", "repo"})

    @api.model_create_multi
    def create(self, vals_list):
        """Sync GitHub metadata for newly inserted github.com repositories.

        Args:
            vals_list (list[dict]): Values passed to ``create``.

        Returns:
            recordset: Created or reused repositories.
        """
        existing_ids = set()
        for vals in vals_list:
            url = vals.get("url")
            if not url:
                continue
            repo_id = self._get_repo_id_by_url(
                url=url, create=False, raise_if_invalid=False
            )
            if repo_id:
                existing_ids.add(repo_id)
        repos = super(
            CxTowerGitRepo,
            self.with_context(
                git_github_sync_depth=1,
                git_github_sync_skip_inverse=True,
            ),
        ).create(vals_list)
        repos = repos.with_env(self.env)
        to_sync = repos.filtered(lambda item: item.id not in existing_ids)
        if to_sync:
            to_sync.with_context(git_github_sync_raise=False).action_git_github_sync()
        return repos

    def write(self, vals):
        """Sync GitHub metadata when URL-related fields change.

        Args:
            vals (dict): Values passed to ``write``.

        Returns:
            bool: Result of ``write``.
        """
        if self.env.context.get("git_github_sync_depth", 0) > 0:
            return super().write(vals)
        sync_fields = self._SYNC_WRITE_FIELDS.intersection(vals) - {"url"}
        res = super(CxTowerGitRepo, self.with_context(git_github_sync_depth=1)).write(
            vals
        )
        # A URL write already syncs from ``_inverse_url``. Syncing again
        # here would send a second GET for the same save.
        if sync_fields and "url" not in vals:
            self.with_context(git_github_sync_raise=False).action_git_github_sync()
        return res

    def _inverse_url(self):
        """After parsing a URL, read GitHub metadata for github.com repositories."""
        super()._inverse_url()
        if self.env.context.get("git_github_sync_skip_inverse"):
            return
        if self.env.context.get("git_github_sync_depth") == 1:
            self.with_context(git_github_sync_raise=False).action_git_github_sync()

    def action_git_github_sync(self):
        """Read GitHub repository metadata for github.com repositories.

        Uses the repository Secret, the owner Secret, or the GitHub API
        Secret setting. Interactive calls raise ``UserError`` when GitHub
        cannot be read. They do not catch ``AccessError``. Saves during
        create or write log at info and keep the form valid, including
        when the owner id cannot be written.

        Raises:
            UserError: No secret resolves, or GitHub did not return a
                usable repository payload. Only on an interactive call.
            AccessError: The caller cannot write this repository, or, on
                an interactive call, cannot write the owner's GitHub id.

        Returns:
            dict | bool: Wizard action when an owner id must be confirmed,
            otherwise ``False``.
        """
        raise_errors = self.env.context.get("git_github_sync_raise", True)
        GitRemote = self.env["cx.tower.git.remote"]
        wizard_lines = []
        for repo in self:
            repo._git_github_sync_one(GitRemote, raise_errors, wizard_lines)
        if wizard_lines:
            lines = list({line["owner_id"]: line for line in wizard_lines}.values())
            wizard = self.env["cx.tower.git.github.sync.wizard"].create(
                {"line_ids": [(0, 0, line) for line in lines]}
            )
            return {
                "name": self.env._("Confirm GitHub owner id"),
                "type": "ir.actions.act_window",
                "res_model": "cx.tower.git.github.sync.wizard",
                "res_id": wizard.id,
                "view_mode": "form",
                "target": "new",
            }
        return False

    def _git_github_sync_one(self, git_remote, raise_errors, wizard_lines):
        """Apply the GitHub sync logic to one repository.

        Args:
            git_remote (cx.tower.git.remote): Remote model for token helpers.
            raise_errors (bool): Whether to raise ``UserError``.
            wizard_lines (list[dict]): Wizard line values to append on clash.

        Raises:
            UserError: No secret resolves, or GitHub did not return a
                usable repository payload, when ``raise_errors`` is set.
            AccessError: The caller cannot write this repository, or,
                when ``raise_errors`` is set, cannot write the owner's
                GitHub id. A quiet save catches that owner error.

        Returns:
            bool: ``False``. A clash is recorded on ``wizard_lines``.
        """
        self.ensure_one()
        repo = self
        if repo.provider != "github" or repo.host != "github.com":
            repo.write({"github_repo_ref": False})
            return False
        reference = git_remote._git_head_api_reference(repo)
        if not reference:
            if raise_errors:
                raise UserError(
                    self.env._(
                        "No GitHub API secret is configured for this repository."
                    )
                )
            _logger.info(
                "Skipping GitHub repository read for %s: no secret resolves.",
                repo.display_name,
            )
            repo.write({"github_repo_ref": False})
            return False
        try:
            token = git_remote._git_head_api_token(repo, server=None, partner=None)
        except UserError:
            if raise_errors:
                raise
            _logger.info(
                "Skipping GitHub repository read for %s: no secret value resolves.",
                repo.display_name,
            )
            repo.write({"github_repo_ref": False})
            return False
        try:
            payload = repo._git_github_fetch_repo(token, git_remote)
        except UserError as error:
            if raise_errors:
                raise
            _logger.info(
                "GitHub repository read failed for %s: %s",
                repo.display_name,
                error.args[0] if error.args else error,
            )
            repo.write({"github_repo_ref": False})
            return False
        return repo._git_github_apply_payload(payload, raise_errors, wizard_lines)

    def _git_github_fetch_repo(self, token, git_remote):
        """Call GitHub for one repository and return the JSON object.

        Args:
            token (str): Bearer token.
            git_remote (cx.tower.git.remote): Remote model for error text.

        Returns:
            dict: GitHub repository payload.

        Raises:
            UserError: When GitHub cannot be reached or the body is invalid.
        """
        self.ensure_one()
        owner = self.owner_id.name
        name = self.repo
        if not owner or not name:
            raise UserError(self.env._("GitHub returned an unexpected response."))
        url = git_remote._git_github_repos_base(owner, name)
        try:
            response = requests.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                    "Authorization": f"Bearer {token}",
                },
                timeout=10,
            )
        except RequestException as error:
            raise UserError(self.env._("GitHub could not be reached.")) from error
        if response.status_code != 200:
            raise UserError(git_remote._git_github_error_message(response))
        try:
            payload = response.json()
        except ValueError as error:
            raise UserError(
                self.env._("GitHub returned an unexpected response.")
            ) from error
        if not isinstance(payload, dict) or not self._git_github_payload_valid(payload):
            raise UserError(self.env._("GitHub returned an unexpected response."))
        return payload

    @api.model
    def _git_github_payload_valid(self, payload):
        """Return whether ``payload`` has the fields Tower stores.

        Args:
            payload (object): Parsed JSON body.

        Returns:
            bool: True when ``id``, ``private``, and ``owner.id`` are valid.
        """
        if not isinstance(payload, dict):
            return False
        repo_id = payload.get("id")
        if not isinstance(repo_id, Integral) or isinstance(repo_id, bool):
            return False
        if not isinstance(payload.get("private"), bool):
            return False
        owner = payload.get("owner")
        if not isinstance(owner, dict):
            return False
        owner_id = owner.get("id")
        if not isinstance(owner_id, Integral) or isinstance(owner_id, bool):
            return False
        return True

    def _git_github_apply_payload(self, payload, raise_errors, wizard_lines):
        """Write repository fields and optionally update the owner id.

        Args:
            payload (dict): GitHub repository payload.
            raise_errors (bool): Whether owner clashes open the wizard.
            wizard_lines (list[dict]): Wizard lines to extend on clash.

        Returns:
            bool: False; wizard action is built from ``wizard_lines``.
        """
        self.ensure_one()
        repo = self
        fetched_owner_ref = str(payload["owner"]["id"])
        repo_vals = {
            "github_repo_ref": str(payload["id"]),
            "is_private": payload["private"],
        }
        owner = repo.owner_id
        stored = owner.github_owner_ref if owner else False

        repo.write(repo_vals)

        if not owner:
            return False
        if not stored or stored == fetched_owner_ref:
            try:
                owner.write({"github_owner_ref": fetched_owner_ref})
            except AccessError:
                if raise_errors:
                    raise
                _logger.info(
                    "GitHub owner id not stored for %s: access denied on owner.",
                    repo.display_name,
                )
            return False
        if not raise_errors:
            return False
        wizard_lines.append(
            {
                "owner_id": owner.id,
                "stored_github_owner_ref": stored,
                "fetched_github_owner_ref": fetched_owner_ref,
            }
        )
        return False
