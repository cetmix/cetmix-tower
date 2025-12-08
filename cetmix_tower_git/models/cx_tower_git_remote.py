# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import giturlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerGitRemote(models.Model):
    """
    Git Remote.
    Implements single git remote.
    Eg a branch or a pull request.
    """

    _name = "cx.tower.git.remote"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.yaml.mixin",
    ]
    _description = "Cetmix Tower Git Remote"
    _order = "sequence, name"

    active = fields.Boolean(related="source_id.active", store=True, readonly=True)
    enabled = fields.Boolean(
        default=True, help="Enable in configuration and exported to files"
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(compute="_compute_name", store=True, default="remote")
    source_id = fields.Many2one(
        comodel_name="cx.tower.git.source",
        required=True,
        ondelete="cascade",
        auto_join=True,
    )
    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        related="source_id.git_project_id",
        store=True,
        readonly=True,
    )
    repo_id = fields.Many2one(
        comodel_name="cx.tower.git.repo",
        string="Repository",
        required=True,
        ondelete="restrict",
        help="If selected, the remote URL will be filled from the"
        " repo settings based on the remote protocol",
    )
    repo_provider = fields.Selection(
        related="repo_id.provider",
        readonly=True,
    )
    # -- Repo related fields
    url_protocol = fields.Selection(
        string="Protocol",
        selection=[
            ("ssh", "SSH"),
            ("https", "HTTPS"),
            ("git", "GIT"),
        ],
        required=True,
        default=lambda self: self._get_default_url_protocol(),
    )
    is_private = fields.Boolean(
        string="Private",
        help="Repository is private",
        related="repo_id.is_private",
        store=True,
        readonly=True,
    )
    head_type = fields.Selection(
        selection=[
            ("branch", "Branch"),
            ("pr", "Pull/Merge Request"),
            ("commit", "Commit"),
        ],
        required=True,
    )
    head = fields.Char(
        help="Git remote head. Link to branch, PR, commit or commit hash.",
        required=True,
        index=True,
    )

    def _get_default_url_protocol(self):
        """Default URL protocol for new remote.

        Returns:
            Char: Default URL protocol.
        """
        return "https"

    @api.depends("source_id", "sequence")
    def _compute_name(self):
        """
        Compute remote name.
        By default all remotes are named `remote_<position>`
        where position is the position of the remote in the source.
        Eg first remote is `remote_1`, second is `remote_2`, etc.
        """
        for remote in self:
            if remote.source_id:
                for index, source_remote in enumerate(remote.source_id.remote_ids):
                    source_remote.name = f"remote_{index + 1}"

    @api.onchange("head")
    def onchange_head(self):
        """
        Extract head number from head url
        and set it as head.
        """
        for remote in self:
            if remote.head and "/" in remote.head:
                remote.head = self._sanitize_head(remote.head)

    @api.model_create_multi
    def create(self, vals_list):
        # Sanitize head
        for vals in vals_list:
            head = vals.get("head")
            if head and "/" in head:
                vals["head"] = self._sanitize_head(head)
        res = super().create(vals_list)
        # Export project to related files and templates
        res._update_related_files_and_templates()
        return res

    def write(self, vals):
        # Sanitize head
        if "head" in vals:
            head = vals["head"]
            if head and "/" in head:
                vals["head"] = self._sanitize_head(head)
        res = super().write(vals)
        # Update related files and templates on update
        self._update_related_files_and_templates()
        return res

    def unlink(self):
        """
        Override to update related files and templates on unlink
        """
        projects = self.git_project_id
        res = super().unlink()

        # Update related files and templates on unlink
        if projects:
            file_relations = projects.git_project_rel_ids  # type: ignore
            if file_relations:
                file_relations._save_to_file()
            template_relations = projects.git_project_file_template_rel_ids  # type: ignore
            if template_relations:
                template_relations._save_to_file_template()
        return res

    def _sanitize_head(self, head):
        """Sanitize head.
        Extract head number from head url
        and set it as head.

        Args:
            head (Char): Head to sanitize

        Returns:
            Char: Sanitized head
        """
        if head and "/" in head:
            return head.split("/")[-1].strip()
        return head

    def _update_related_files_and_templates(self):
        # Update related files on update
        related_files = self.mapped("git_project_id").mapped("git_project_rel_ids")
        if related_files:
            related_files._save_to_file()
        related_templates = self.mapped("git_project_id").mapped(
            "git_project_file_template_rel_ids"
        )
        if related_templates:
            related_templates._save_to_file_template()

    # ------------------------------
    # Reference mixin methods
    # ------------------------------
    def _get_pre_populated_model_data(self):
        res = super()._get_pre_populated_model_data()
        res.update({"cx.tower.git.remote": ["cx.tower.git.source", "source_id"]})
        return res

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "enabled",
            "sequence",
            "repo_id",
            "head",
            "head_type",
        ]
        return res

    # ------------------------------
    # Git Aggregator related methods
    # ------------------------------
    def _git_aggregator_prepare_url(self):
        """Prepare url for git aggregator

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()

        if not self.repo_id:
            raise ValidationError(_("Repository is required"))
        if not self.repo_id.url:
            raise ValidationError(_("Repository URL is not set"))

        url = self.repo_id.url
        prepared_url = giturlparse.parse(url).urls.get(self.url_protocol, url)

        # If repo is public or is not using HTTPS protocol return URL as is
        if not self.is_private or self.url_protocol != "https":
            return prepared_url

        if self.repo_provider == "github":
            prepared_url = self._git_aggregator_prepare_url_github(prepared_url)
        elif self.repo_provider == "gitlab":
            prepared_url = self._git_aggregator_prepare_url_gitlab(prepared_url)
        elif self.repo_provider == "bitbucket":
            prepared_url = self._git_aggregator_prepare_url_bitbucket(prepared_url)

        return prepared_url

    def _git_aggregator_prepare_authenticated_url(self, url, auth_token):
        """Helper to inject authentication token into HTTPS URL.

        Args:
            url (Char): URL to prepare
            auth_token (Char): Authentication token

        Returns:
            Char: Prepared url for git aggregator
        """
        url_without_protocol = url.replace("https://", "")
        return f"https://{auth_token}@{url_without_protocol}"

    def _git_aggregator_prepare_url_github(self, url):
        """
        Prepare url for git aggregator for private Github repo
        using https protocol.

        Args:
            url (Char): URL to prepare

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()
        return self._git_aggregator_prepare_authenticated_url(
            url,
            "$GITHUB_TOKEN:x-oauth-basic",
        )

    def _git_aggregator_prepare_url_gitlab(self, url):
        """
        Prepare url for git aggregator for private GitLab repo
        using https protocol.

        Args:
            url (Char): URL to prepare

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()
        return self._git_aggregator_prepare_authenticated_url(
            url, "$GITLAB_TOKEN_NAME:$GITLAB_TOKEN"
        )

    def _git_aggregator_prepare_url_bitbucket(self, url):
        """
        Prepare url for git aggregator for private Bitbucket repo
        using https protocol.

        Args:
            url (Char): URL to prepare

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()
        return self._git_aggregator_prepare_authenticated_url(
            url, "x-token-auth:$BITBUCKET_TOKEN"
        )

    def _git_aggregator_prepare_head(self):
        """Prepare head for git aggregator

        Returns:
            Char: Prepared head for git aggregator
        """
        self.ensure_one()
        if self.repo_provider == "github":
            return self._git_aggregator_prepare_head_github()
        if self.repo_provider == "gitlab":
            return self._git_aggregator_prepare_head_gitlab()
        if self.repo_provider == "bitbucket":
            return self._git_aggregator_prepare_head_bitbucket()
        return self.head

    def _extract_head_number(self):
        """
        Extract the last component from head
        (branch name, PR number, or commit hash).

        Raises:
            ValidationError: If head number is empty

        Returns:
            Char: Extracted head number
        """
        self.ensure_one()
        head_number = self.head.split("/")[-1]
        if not head_number:
            raise ValidationError(
                _("Git Aggregator: Head number is empty in %(head)s", head=self.head)
            )
        return head_number

    def _git_aggregator_prepare_head_github(self):
        """Prepare head for git aggregator for Github.

        Returns:
            Char: Prepared head for git aggregator
        """
        self.ensure_one()
        head_number = self._extract_head_number()
        # PR/MR
        if self.head_type == "pr":
            return f"refs/pull/{head_number}/head"

        # Commit
        if self.head_type in ["commit", "branch"]:
            return f"{head_number}"

        # Fallback to original head
        return self.head

    def _git_aggregator_prepare_head_gitlab(self):
        """Prepare head for git aggregator for GitLab.

        Returns:
            Char: Prepared head for git aggregator
        """
        self.ensure_one()
        head_number = self._extract_head_number()
        # PR/MR
        if self.head_type == "pr":
            return f"merge-requests/{head_number}/head"

        # Commit
        # https://gitlab.com/cetmix/test/-/list/17.0-test-branch?ref_type=heads
        if self.head_type in ["commit", "branch"]:
            head_parts = head_number.split("?")
            return f"{head_parts[0]}"

        # Fallback to original head
        return self.head

    def _git_aggregator_prepare_head_bitbucket(self):
        """Prepare head for git aggregator for Bitbucket.

        Returns:
            Char: Prepared head for git aggregator
        """
        self.ensure_one()
        # PR/MR
        if self.head_type == "pr":
            raise ValidationError(
                _(
                    "Git Aggregator: "
                    "Bitbucket does not support"
                    " fetching PRs. Please use branch instead.\n\n"
                    "Source: %(src)s\n"
                    "URL: %(url)s\n"
                    "Head: %(head)s",
                    src=self.source_id.name,
                    url=self.repo_id.url,
                    head=self.head,
                )
            )

        head_number = self._extract_head_number()
        # Commit
        if self.head_type in ["commit", "branch"]:
            return f"{head_number}"

        # Fallback to original head
        return self.head
