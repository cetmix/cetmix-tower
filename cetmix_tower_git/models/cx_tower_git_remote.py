# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from urllib.parse import urlparse

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
    url = fields.Char(
        required=True,
        string="URL",
        help="Git remote URL. Eg 'https://github.com/cetmix/cetmix-tower.git'"
        " or 'git@github.com:cetmix/cetmix-tower.git'",
    )
    head_type = fields.Selection(
        selection=[
            ("branch", "Branch"),
            ("pr", "Pull/Merge Request"),
            ("commit", "Commit"),
        ],
        compute="_compute_head_type",
        store=True,
        readonly=False,
    )
    head = fields.Char(
        required=True,
        help="Git remote head. Link to branch, PR, commit or commit hash."
        " Leave blank to auto-detect",
    )
    is_private = fields.Boolean(help="Repository is private")

    # -- Helper fields
    url_protocol = fields.Selection(
        string="URL Protocol",
        selection=[
            ("ssh", "SSH"),
            ("https", "HTTPS"),
        ],
        compute="_compute_repo_provider",
        store=True,
    )
    repo_provider = fields.Selection(
        string="Repository Provider",
        selection=[
            ("github", "GitHub"),
            ("gitlab", "GitLab"),
            ("bitbucket", "Bitbucket"),
            ("other", "Other"),
        ],
        compute="_compute_repo_provider",
        store=True,
        readonly=False,
        help="Will be tried to be determined from the URL."
        " Please select manually if auto-detection fails.",
    )

    @api.constrains("url")
    def _check_url(self):
        """Check if the URL is valid.

        Raises:
            ValidationError: if the URL is not valid.
        """
        for remote in self:
            if remote.url:
                url = remote.url.lower()
                if not url.endswith(".git"):
                    raise ValidationError(
                        _("Not a valid URL. URL must end with '.git'")
                    )
                if not url.startswith("https://") and not url.startswith("git@"):
                    raise ValidationError(
                        _("Not a valid URL. URL must start with 'https://' or 'git@'")
                    )

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

    @api.depends("url")
    def _compute_repo_provider(self):
        for remote in self:
            if remote.url:
                remote.update(self._get_repo_protocol_and_provider_from_url(remote.url))

    @api.depends("head")
    def _compute_head_type(self):
        for remote in self:
            if remote.head:
                remote.head_type = self._get_head_type_from_head(remote.head)

    @api.onchange("url")
    def _onchange_url(self):
        self._check_url()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Export project to related files
        res._update_related_files()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Update related files on update
        self._update_related_files()
        return res

    def _update_related_files(self):
        # Update related files on update
        related_files = (
            self.mapped("source_id")
            .mapped("git_project_id")
            .mapped("git_project_rel_ids")
        )
        if related_files:
            related_files._save_to_file()

    def _get_repo_protocol_and_provider_from_url(self, repo_url):
        """Parse repository URL and return protocol and provider.

        Args:
            url (Char): Repository URL

        Returns:
            Dict: Protocol and provider
                {
                    "url_protocol": "ssh" | "https",
                    "repo_provider": "github" | "gitlab" | "bitbucket" | "other",
                }
        """
        # TODO: this is still not the best solution.
        # To be replaced with https://github.com/nephila/giturlparse
        # or similar when migrating to newer Odoo versions.
        url = repo_url.lower()

        # Determine repo protocol
        if url.startswith("git@"):
            url_protocol = "ssh"
            # To parse hostname using urlparse
            url = url.replace(":", "/").replace("git@", "http://")
        elif url.startswith("https://"):
            url_protocol = "https"
        else:
            url_protocol = None

        # Determine repository provider by URL
        repo_provider = "other"
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if hostname:
            hostname_parts = hostname.split(".")
            if len(hostname_parts) < 2:
                raise ValidationError(
                    _(
                        "Not a valid URL: %(url_msg)s\n"
                        "URL must contain at least two parts"
                        " separated by dot.",
                        url_msg=url,
                    )
                )
            provider_slug = hostname_parts[-2]
            if provider_slug == "github":
                repo_provider = "github"
            elif provider_slug in ["gitlab", "gitlab.org"]:
                repo_provider = "gitlab"
            elif provider_slug in ["bitbucket", "bitbucket.org"]:
                repo_provider = "bitbucket"

        return {
            "url_protocol": url_protocol,
            "repo_provider": repo_provider,
        }

    def _get_head_type_from_head(self, head):
        """Parse head and return head type.

        Args:
            head (Char): Head

        Returns:
            Char: head type
        """
        head_parts = head.lower().split("/")
        if (
            "pr" in head_parts
            or "pull" in head_parts
            or "merge_requests" in head_parts
            or "pull-requests" in head_parts
        ):
            head_type = "pr"
        elif "commit" in head_parts or "commits" in head_parts:
            head_type = "commit"
        else:
            head_type = "branch"
        return head_type

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
            "is_private",
            "url",
            "repo_provider",
            "head",
            "head_type",
        ]
        return res

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    # Git Aggregator related methods
    # ------------------------------
    def _git_aggregator_prepare_url(self):
        """Prepare url for git aggregator

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()

        if not self.url:
            raise ValidationError(_("URL is required"))

        # If repo is public or using SSH protocol return URL as is
        if not self.is_private or self.url_protocol == "ssh":
            return self.url

        if self.repo_provider == "github":
            url = self._git_aggregator_prepare_url_github()
        elif self.repo_provider == "gitlab":
            url = self._git_aggregator_prepare_url_gitlab()
        elif self.repo_provider == "bitbucket":
            url = self._git_aggregator_prepare_url_bitbucket()
        else:
            url = self.url
        return url

    def _git_aggregator_prepare_url_github(self):
        """Prepare url for git aggregator
        for private Github repo using https protocol.

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()

        # This is how final url will look like
        # https://$GITHUB_TOKEN:x-oauth-basic@github.com/soem_org/some_private_repo.git
        url_without_protocol = self.url.replace("https://", "")
        url = f"https://$GITHUB_TOKEN:x-oauth-basic@{url_without_protocol}"
        return url

    def _git_aggregator_prepare_url_gitlab(self):
        """Prepare url for git aggregator
        for private GitLab repo using https protocol.

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()

        # This is how final url will look like
        # https://<token-name>:<token-value>@<gitlaburl-repository>.git
        url_without_protocol = self.url.replace("https://", "")
        url = f"https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@{url_without_protocol}"
        return url

    def _git_aggregator_prepare_url_bitbucket(self):
        """Prepare url for git aggregator
        for private Github repo using https protocol.

        Returns:
            Char: Prepared url for git aggregator
        """
        self.ensure_one()

        # This is how final url will look like
        # https://x-token-auth:{access_token}@bitbucket.org/user/repo.git
        # From https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/
        url_without_protocol = self.url.replace("https://", "")
        url = f"https://x-oauth-basic:$BITBUCKET_TOKEN@{url_without_protocol}"
        return url

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

    def _git_aggregator_prepare_head_github(self):
        """Prepare head for git aggregator for Github.

        Returns:
            Char: Prepared head for git aggregator
        """

        # Extract branch name, PR/MR or commit number from head
        head_number = self.head.split("/")[-1]
        if not head_number:
            raise ValidationError(
                _("Git Aggregator: " "Head number is empty in %(head)s", head=self.head)
            )

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
        # Extract branch name, PR/MR or commit number from head
        head_number = self.head.split("/")[-1]
        if not head_number:
            raise ValidationError(
                _("Git Aggregator: " "Head number is empty in %(head)s", head=self.head)
            )

        # PR/MR
        if self.head_type == "pr":
            return f"merge-requests/{head_number}/head"

        # Commit
        # https://gitlab.com/cetmix/test/-/tree/17.0-test-branch?ref_type=heads
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
        # Extract branch name, PR/MR or commit number from head
        head_number = self.head.split("/")[-1]
        if not head_number:
            raise ValidationError(
                _("Git Aggregator: " "Head number is empty in %(head)s", head=self.head)
            )
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
                    url=self.url,
                    head=self.head,
                )
            )

        # Commit
        if self.head_type in ["commit", "branch"]:
            return f"{head_number}"

        # Fallback to original head
        return self.head
