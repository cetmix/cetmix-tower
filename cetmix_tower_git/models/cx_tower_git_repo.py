# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

import giturlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import ormcache

_logger = logging.getLogger(__name__)


class CxTowerGitRepo(models.Model):
    """
    Git Repository.
    Represents a git repository with its metadata and configuration.
    """

    _name = "cx.tower.git.repo"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.yaml.mixin",
    ]
    _description = "Cetmix Tower Git Repository"
    _order = "name"
    _rec_names_search = ["repo", "host", "owner_id"]

    active = fields.Boolean(default=True, help="Indicates if the repository is active")
    name = fields.Char(
        compute="_compute_name", store=True, required=False, index="trigram"
    )
    reference = fields.Char(
        index=True,
        compute="_compute_name",
        required=False,
        store=True,
    )
    repo = fields.Char(
        string="Repository Name",
        readonly=True,
        help="Repository name (e.g., 'cetmix-tower', 'odoo')",
    )
    url = fields.Char(
        string="Generic URL",
        help="Displayed in 'https' format, but can be entered in any format",
        compute="_compute_url",
        inverse="_inverse_url",
        required=True,
        compute_sudo=True,
    )
    url_ssh = fields.Char(
        string="SSH URL",
        help="SSH URL of the repository",
        compute="_compute_url",
        compute_sudo=True,
    )
    url_git = fields.Char(
        string="GIT URL",
        help="GIT URL of the repository",
        compute="_compute_url",
        compute_sudo=True,
    )
    is_private = fields.Boolean(
        string="Private", default=False, help="Indicates if the repository is private"
    )
    provider = fields.Selection(
        selection="_selection_provider",
        required=True,
        default="other",
        help="Repository provider to determine provider-based behaviour",
    )
    host = fields.Char(
        readonly=True,
        index=True,
        help="Repository host (e.g., 'github.com', 'gitlab.com')",
    )
    owner_id = fields.Many2one(
        comodel_name="cx.tower.git.repo.owner",
        readonly=True,
        help="Repository owner (e.g., 'cetmix' or 'OCA')",
    )
    secret_id = fields.Many2one(
        comodel_name="cx.tower.key",
        string="Secret",
        domain="[('key_type', '=', 's')]",
        help="Custom secret used for this repository",
    )
    remote_ids = fields.One2many(
        comodel_name="cx.tower.git.remote",
        inverse_name="repo_id",
        help="Remotes that use this repository",
    )
    git_project_ids = fields.Many2many(
        comodel_name="cx.tower.git.project",
        relation="cx_tower_git_repo_project_rel",
        column1="repo_id",
        column2="project_id",
        compute="_compute_git_project_ids",
        store=True,
        help="Projects this repository is used in",
    )
    remote_count = fields.Integer(
        compute="_compute_remote_count",
        help="Number of remotes this repository is used in",
    )
    git_project_count = fields.Integer(
        compute="_compute_git_project_count",
        help="Number of projects this repository is used in",
    )

    _sql_constraints = [
        (
            "unique_repo_host_owner",
            "unique(repo, host, owner_id)",
            "A repository with the same name, host, and owner already exists.",
        ),
    ]

    # -- Selection
    def _selection_provider(self):
        """Available repository providers.

        Returns:
            List of tuples: available options.
        """
        return [
            ("github", "GitHub"),
            ("gitlab", "GitLab"),
            ("bitbucket", "Bitbucket"),
            ("assembla", "Assembla"),
            ("other", "Other"),
        ]

    # -- Computes
    @api.depends("host", "owner_id", "owner_id.name", "repo")
    def _compute_name(self):
        """
        Compute name in format: host/owner/name.
        Compute reference based on name.
        """
        for repo in self:
            if repo.host and repo.owner_id and repo.repo:
                name = f"{repo.host}/{repo.owner_id.name}/{repo.repo}"
                reference = repo._generate_or_fix_reference(name)
                repo.update(
                    {
                        "name": name,
                        "reference": reference,
                    }
                )
            else:
                repo.update(
                    {
                        "name": False,
                        "reference": False,
                    }
                )

    @api.depends("remote_ids", "remote_ids.git_project_id")
    def _compute_git_project_ids(self):
        """Compute projects this repository is used in."""
        for repo in self:
            repo.git_project_ids = repo.remote_ids.git_project_id

    @api.depends("remote_ids")
    def _compute_remote_count(self):
        """Compute remote count field."""
        for repo in self:
            repo.remote_count = len(repo.remote_ids)

    @api.depends("git_project_ids")
    def _compute_git_project_count(self):
        """Compute project count field."""
        for repo in self:
            repo.git_project_count = len(repo.git_project_ids)

    @api.depends("repo", "host", "owner_id")
    def _compute_url(self):
        """Compute URL from repository properties."""
        for repo in self:
            if repo.repo and repo.host and repo.owner_id:
                https_url = f"https://{repo.host}/{repo.owner_id.name}/{repo.repo}.git"
            elif repo.repo and repo.host:
                https_url = f"https://{repo.host}/{repo.repo}.git"
            else:
                https_url = ""
            if https_url:
                try:
                    parsed_urls = giturlparse.parse(https_url).urls
                    urls = {
                        "url": https_url,
                        "url_ssh": parsed_urls["ssh"],
                        "url_git": parsed_urls["git"],
                    }
                except Exception as e:  # noqa: F841 catch all errors
                    _logger.error(
                        "Failed to parse constructed URL '%s' for repo %s",
                        https_url,
                        repo.display_name,
                    )
                    urls = {
                        "url": "",
                        "url_ssh": "",
                        "url_git": "",
                    }
            else:
                urls = {
                    "url": "",
                    "url_ssh": "",
                    "url_git": "",
                }
            repo.update(urls)

    def _inverse_url(self):
        """Parse URL to update repository properties."""
        for repo in self:
            if not repo.url:
                continue
            # Parse URL
            parsed_url_dict = self._parse_url(repo.url)
            # Update repository properties
            repo.update(parsed_url_dict)

    def action_view_remotes(self):
        """Open remotes list view."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_git.action_cx_tower_git_remote"
        )
        action.update(
            {
                "domain": [("repo_id", "=", self.id)],
                "context": {"default_repo_id": self.id},
            }
        )
        return action

    def action_view_projects(self):
        """Open projects list view."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_git.cx_tower_git_project_action"
        )
        action.update(
            {
                "domain": [("repo_ids", "in", self.id)],
                "context": {"default_repo_ids": [(4, self.id)]},
            }
        )
        return action

    @api.model_create_multi
    def create(self, vals_list):
        """Create multiple repositories."""
        # Check if any of the repositories already exist
        # This is needed to allow creating repositories using just an URL.
        # Eg when importing repositories from a YAML file.
        res = self.browse()
        existing_repo_ids = []
        vals_list_to_create = []
        for vals in vals_list:
            url = vals.get("url")
            if url:
                # Try to get repository by URL
                repo_id = self._get_repo_id_by_url(
                    url=url, create=False, raise_if_invalid=False
                )
                if repo_id:
                    existing_repo_ids.append(repo_id)
                    continue
                # Parse URL and update vals
                parsed_url_dict = self._parse_url(url=url, raise_if_invalid=True)
                vals.update(parsed_url_dict)
            # Add to create list (with or without URL)
            vals_list_to_create.append(vals)
        # Compose the result
        if vals_list_to_create:
            res |= super().create(vals_list_to_create)
        if existing_repo_ids:
            res |= self.browse(existing_repo_ids)
        self.env.registry.clear_cache()
        return res

    def write(self, vals):
        """Write repositories."""
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        """Unlink repositories."""
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    @api.model
    def name_create(self, name):
        """
        Create a new repository from a URL.
        """
        repo_id = self._get_repo_id_by_url(url=name, create=True, raise_if_invalid=True)
        repo = self.browse(repo_id)

        return repo_id, repo.display_name

    @ormcache("self.env.uid", "self.env.su", "url", "create", "raise_if_invalid")
    def _get_repo_id_by_url(self, url, create=False, raise_if_invalid=False):
        """Get repository id by URL.

        Args:
            url (Char): URL to get repository id
            create (Bool, optional): Create repository if not found.
                Default is False.
            raise_if_invalid (Bool, optional): Raise ValidationError
                if the URL is not valid. Default is False.

        Returns:
            int: Repository ID
            or False if the URL is not valid and raise_if_invalid is False

        Raises:
            ValidationError: If the URL is not valid and raise_if_invalid is True
        """
        # Parse URL
        parsed_url_dict = self._parse_url(url, raise_if_invalid=raise_if_invalid)
        if not parsed_url_dict:
            return False

        # Check if repository already exists and use it
        repo = self.search(
            [
                ("repo", "=", parsed_url_dict["repo"]),
                ("host", "=", parsed_url_dict["host"]),
                ("owner_id", "=", parsed_url_dict["owner_id"]),
            ],
            limit=1,
        )

        # Otherwise, create a new one
        if not repo and create:
            repo = self.create(parsed_url_dict)

        return repo.id if repo else False

    def _parse_url(self, url, raise_if_invalid=True):
        """Parse URL to get name, host and owner.

        Args:
            url (Char): URL to parse

        Raises:
            ValidationError: If the URL is not valid

        Returns:
            Dict: Dictionary with name, host and owner
            or empty dict if the URL is not valid and raise_if_invalid is False
        """

        # Validate URL
        if not giturlparse.validate(url):
            if raise_if_invalid:
                raise ValidationError(_("Not a valid repository URL!"))
            return {}

        # Parse URL
        parsed_url = giturlparse.parse(url)

        # Get or create owner
        owner_id = self.env["cx.tower.git.repo.owner"]._get_owner_id_by_name(
            name=parsed_url.owner,
            create=True,
        )

        # Get provider based on host
        provider = self._get_provider(parsed_url)

        return {
            "repo": parsed_url.repo,
            "host": parsed_url.host,
            "owner_id": owner_id,
            "provider": provider,
        }

    def _get_provider(self, parsed_url):
        """Get provider.

        Args:
            parsed_url (GitUrlParsed): Parsed URL object

        Returns:
            str: Provider name
        """
        provider = "other"
        if parsed_url.assembla:
            provider = "assembla"
        elif parsed_url.bitbucket or "bitbucket" in parsed_url.host:
            provider = "bitbucket"
        elif parsed_url.gitlab:
            provider = "gitlab"
        elif parsed_url.github:
            provider = "github"

        return provider

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "url",
            "is_private",
            "secret_id",
        ]
        return res
