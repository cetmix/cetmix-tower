# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import giturlparse

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        default=True,
        help="Enable in configuration and exported to files",
        yaml_export=True,
    )
    sequence = fields.Integer(default=10, yaml_export=True)
    name = fields.Char(
        compute="_compute_name", store=True, default="remote", yaml_export=True
    )
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
        ondelete="cascade",
    )
    repo_id = fields.Many2one(
        comodel_name="cx.tower.git.repo",
        string="Repository",
        required=True,
        ondelete="restrict",
        help="If selected, the remote URL will be filled from the"
        " repo settings based on the remote protocol",
        yaml_export="include",
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
        yaml_export=True,
    )
    head = fields.Char(
        help="Git remote head. Link to branch, PR, commit or commit hash.",
        required=True,
        index=True,
        yaml_export=True,
    )
    head_reference = fields.Char(
        store=False,
        help="Aggregator value sent with a captioned suggestion. "
        "Selecting a row stores this instead of the visible text.",
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

    @api.onchange("head", "head_reference")
    def onchange_head(self):
        """Store a selected reference, and reduce a pasted link to its tail.

        A provider can send the visible suggestion in ``head`` and the
        aggregator value in ``head_reference``. The reference replaces
        ``head`` and is then cleared, so a later edit of Head is kept.
        """
        for remote in self:
            if self._head_reference_value(remote.head_reference):
                remote.head = self._head_reference_value(remote.head_reference)
                remote.head_reference = False
            elif remote.head and "/" in remote.head:
                remote.head = self._sanitize_head(remote.head)

    @api.model_create_multi
    def create(self, vals_list):
        """Sanitize ``head`` and apply a selected reference.

        Args:
            vals_list (list[dict]): Values passed to ``create``.

        Returns:
            recordset: Created remotes.
        """
        for vals in vals_list:
            head = vals.get("head")
            if head and "/" in head:
                vals["head"] = self._sanitize_head(head)
            self._apply_head_reference(vals)
        res = super().create(vals_list)
        # Export project to related files and templates
        res._update_related_files_and_templates()
        return res

    def write(self, vals):
        """Sanitize ``head`` and apply a selected reference.

        Args:
            vals (dict): Values passed to ``write``.

        Returns:
            bool: Result of ``write``.
        """
        if "head" in vals:
            head = vals["head"]
            if head and "/" in head:
                vals["head"] = self._sanitize_head(head)
        self._apply_head_reference(vals)
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

        # Update related files on unlink
        if projects:
            file_relations = projects.git_project_rel_ids  # type: ignore
            if file_relations:
                file_relations._save_to_file()
        return res

    def _head_reference_value(self, reference):
        """Return the trimmed storage value from a suggestion.

        Args:
            reference (str | bool | None): ``head_reference`` from the form.

        Returns:
            str: Trimmed value, or an empty string when there is nothing
            to store.
        """
        if not isinstance(reference, str):
            return ""
        return reference.strip()

    def _apply_head_reference(self, vals):
        """Replace ``head`` when the suggestion carried a storage value.

        ``head_reference`` is not stored. It is removed from ``vals`` so
        create and write do not receive it.

        Args:
            vals (dict): Create or write values, modified in place.

        Returns:
            None
        """
        reference = self._head_reference_value(vals.get("head_reference"))
        if reference:
            vals["head"] = reference
        vals.pop("head_reference", None)

    def _sanitize_head(self, head):
        """Keep a typed head, and reduce a pasted link to its last segment.

        A branch name such as ``feat/2233`` contains ``/`` and must be stored
        whole. Only a value that contains ``://`` is a pasted link.

        Args:
            head (Char): Head to sanitize.

        Returns:
            Char: Trimmed head, or the last path segment of a pasted link.
        """
        if not head:
            return head
        head = head.strip()
        if "://" in head:
            return head.split("/")[-1].strip()
        return head

    def _update_related_files_and_templates(self):
        # Update related files on update
        related_files = self.mapped("git_project_id").mapped("git_project_rel_ids")
        if related_files:
            related_files._save_to_file()

    # ------------------------------
    # Reference mixin methods
    # ------------------------------
    def _get_pre_populated_model_data(self):
        res = super()._get_pre_populated_model_data()
        res.update({"cx.tower.git.remote": ["cx.tower.git.source", "source_id"]})
        return res

    # ------------------------------
    # Head autocomplete
    # ------------------------------
    @api.model
    def git_head_autocomplete(self, value):
        """Return Head suggestions for the repository in the field context.

        The autocomplete widget calls this on focus with ``False`` and, while
        typing, with the trimmed string. A provider module fills the rows.
        This method does not call GitHub.

        Args:
            value (str | bool): Trimmed input, or ``False`` when the field
                is focused and still empty.

        Raises:
            AccessError: When the current user cannot write Git remotes.

        Returns:
            list[dict]: Rows ``{"head": "<value>"}``. A provider may also
            set ``head_reference`` to the value that must be stored.
            Empty when the repository is missing, unreadable, or the
            provider has no hook.
        """
        self.browse().check_access("write")
        repo = self._git_head_context_record(
            "cx.tower.git.repo", self.env.context.get("git_repo_id")
        )
        if not repo:
            return []
        source = self._git_head_context_record(
            "cx.tower.git.source", self.env.context.get("git_source_id")
        )
        context_server = self._git_head_context_record(
            "cx.tower.server", self.env.context.get("git_server_id")
        )
        server, partner = self._git_head_autocomplete_scope(source, context_server)
        query = value.strip() if isinstance(value, str) else False
        if query == "":
            query = False
        return self._git_fetch_heads(
            repo,
            self.env.context.get("git_head_type"),
            query,
            server=server,
            partner=partner,
        )

    @api.model
    def _git_head_context_record(self, model_name, res_id):
        """Load one context id when the current user can read it.

        An empty, invalid, or unreadable id is ignored. The raw integer is
        not returned, so it cannot be passed into secret resolution.

        Args:
            model_name (str): Model to browse.
            res_id (int | str | bool): Record id from the field context.

        Returns:
            recordset: The record, or an empty recordset.
        """
        records = self.env[model_name]
        if not res_id:
            return records.browse()
        try:
            res_id = int(res_id)
        except (TypeError, ValueError):
            return records.browse()
        record = records.browse(res_id).exists()
        if not record or not record.has_access("read"):
            return records.browse()
        return record

    @api.model
    def _git_head_autocomplete_scope(self, source, server):
        """Choose the server and partner used to resolve the API secret.

        On the Jet list the checked server is used, and the partner only when
        it is the partner of a Jet the user can read on that server. On the
        remote form, a project with one Jet uses that Jet. A project with no
        Jet and one linked server uses that server and its partner. Several
        Jets or servers leave both empty, so only a global secret can match.

        Args:
            source (cx.tower.git.source): Checked source, or empty.
            server (cx.tower.server): Checked server from the Jet list, or
                empty.

        Returns:
            tuple: ``(server, partner)`` recordsets. Either may be empty.
        """
        partner = self.env["res.partner"].browse()
        if server:
            partner_id = self.env.context.get("git_partner_id")
            try:
                partner_id = int(partner_id) if partner_id else False
            except (TypeError, ValueError):
                partner_id = False
            if partner_id:
                jet = self.env["cx.tower.jet"].search(
                    [
                        ("server_id", "=", server.id),
                        ("partner_id", "=", partner_id),
                    ],
                    limit=1,
                )
                if jet:
                    partner = jet.partner_id
            return server, partner
        if not source:
            return self.env["cx.tower.server"].browse(), partner
        project = source.git_project_id
        jets = self.env["cx.tower.jet"].search([("git_project_id", "=", project.id)])
        if len(jets) == 1:
            jet_server = jets.server_id
            if jet_server and jet_server.has_access("read"):
                return jet_server, jets.partner_id
            return self.env["cx.tower.server"].browse(), partner
        if jets:
            return self.env["cx.tower.server"].browse(), partner
        servers = project.server_ids.filtered(lambda item: item.has_access("read"))
        if len(servers) == 1:
            return servers, servers.partner_id
        return self.env["cx.tower.server"].browse(), partner

    def _git_fetch_heads(self, repo, head_type, query, server=None, partner=None):
        """Dispatch Head suggestions to the repository provider.

        Args:
            repo (cx.tower.git.repo): Repository already checked for read.
            head_type (str): ``branch``, ``pr``, or ``commit``.
            query (str | bool): Trimmed input, or ``False`` on focus.
            server (cx.tower.server | None): Server for the secret, or empty.
            partner (res.partner | None): Partner for the secret, or empty.

        Returns:
            list[dict]: Provider rows, or an empty list when the provider
            has no hook. The repository host is not checked here.
        """
        method = getattr(self, f"_git_fetch_heads_{repo.provider}", None)
        if not method:
            return []
        return method(
            repo, head_type, query, server=server or None, partner=partner or None
        )

    def _git_head_api_token(self, repo, server=None, partner=None):
        """Resolve the Bearer token for a repository API call.

        The repository Secret wins. A provider module can add another
        reference when that Secret is empty. The search order is server
        and partner, then server, then partner, then global.

        Args:
            repo (cx.tower.git.repo): Repository whose secret is resolved.
            server (cx.tower.server | None): Checked server, or empty.
            partner (res.partner | None): Checked partner, or empty.

        Raises:
            UserError: When no secret value resolves.

        Returns:
            str: Secret value. Never a raw context id.
        """
        reference = self._git_head_api_reference(repo)
        if not reference:
            raise UserError(
                self.env._("No GitHub API secret is configured for this repository.")
            )
        kwargs = {}
        if server:
            kwargs["server_id"] = server.id
        if partner:
            kwargs["partner_id"] = partner.id
        token = self.env["cx.tower.key"]._resolve_key_type_secret(reference, **kwargs)
        if not token:
            raise UserError(
                self.env._("No GitHub API secret is configured for this repository.")
            )
        return token

    def _git_head_api_reference(self, repo):
        """Return the secret reference used for the repository API.

        Args:
            repo (cx.tower.git.repo): Repository to read.

        Returns:
            str | bool: Key reference, or a falsy value when none is set.
        """
        if repo.secret_id:
            return repo.secret_id.reference
        return False

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
            raise ValidationError(self.env._("Repository is required"))
        if not self.repo_id.url:
            raise ValidationError(self.env._("Repository URL is not set"))

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
        head = self.head or ""
        if "://" in head:
            head_number = head.split("/")[-1].strip()
        else:
            head_number = head.strip()
        if not head_number:
            raise ValidationError(
                self.env._(
                    "Git Aggregator: Head number is empty in %(head)s",
                    head=self.head,
                )
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
                self.env._(
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
