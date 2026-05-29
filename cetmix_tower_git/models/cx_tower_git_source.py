# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerGitSource(models.Model):
    """
    Git Source.
    Implements single git source.
    Each source can include multiple remotes which can be
    branches or pull requests of different repositories.
    """

    _name = "cx.tower.git.source"
    _description = "Cetmix Tower Git Source"

    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.yaml.mixin",
    ]
    _order = "sequence, name"

    active = fields.Boolean(related="git_project_id.active", store=True, readonly=True)
    enabled = fields.Boolean(
        default=True, help="Enable in configuration and exported to files"
    )
    name = fields.Char(required=False)
    sequence = fields.Integer(default=10)
    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        string="Git Configuration",
        required=True,
        ondelete="cascade",
        auto_join=True,
    )

    remote_ids = fields.One2many(
        comodel_name="cx.tower.git.remote",
        inverse_name="source_id",
        auto_join=True,
        copy=True,
    )
    remote_count = fields.Integer(
        compute="_compute_remote_count",
        string="Remotes",
    )
    remote_count_private = fields.Integer(
        compute="_compute_remote_count",
        string="Private Remotes",
    )

    @api.depends("remote_ids", "remote_ids.enabled", "remote_ids.is_private")
    def _compute_remote_count(self):
        for record in self:
            remote_count = private_remote_count = 0
            for remote in record.remote_ids:
                if not remote.enabled:
                    continue
                if remote.is_private:
                    private_remote_count += 1
                remote_count += 1
            record.update(
                {
                    "remote_count": remote_count,
                    "remote_count_private": private_remote_count,
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Update name
        no_name = res.filtered(lambda s: not s.name)
        if no_name:
            no_name._compose_name()
        # Update related files and templates on create
        res._update_related_files_and_templates()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Compose name
        if "name" in vals and not vals.get("name"):
            self._compose_name()
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

    def _compose_name(self):
        """Compose name if not provided explicitly"""
        for source in self:
            if source.name:
                continue
            remote = fields.first(source.remote_ids)
            if not remote:
                source.name = "Empty Source"
                continue

            remote_repo = remote.repo_id
            if not remote_repo or not remote_repo.owner_id:
                source.name = "Empty Source"
                continue
            source.name = f"{remote_repo.owner_id.name}/{remote_repo.repo}"

    def _update_related_files_and_templates(self):
        # Update related files and templates on update
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
        res.update({"cx.tower.git.source": ["cx.tower.git.project", "git_project_id"]})
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
            "remote_ids",
        ]
        return res

    # ------------------------------
    # Git Aggregator related methods
    # ------------------------------
    def _git_aggregator_prepare_record(self):
        """Prepare json structure for git aggregator.

        Returns:
            Dict: Json structure for git aggregator
        """
        self.ensure_one()

        # Prepare remotes, merges and target
        remotes = {}
        merges = []
        target = None
        for remote in self.remote_ids:
            if remote.enabled:
                remotes.update({remote.name: remote._git_aggregator_prepare_url()})
                merges.append(
                    {
                        "remote": remote.name,
                        "ref": remote._git_aggregator_prepare_head(),
                    }
                )
                # Set target to first remote name
                if not target:
                    target = remote.name

        # If no remotes, return empty dict
        if not remotes:
            return {}

        vals = {
            "remotes": remotes,
            "merges": merges,
            "target": target,
        }

        # Fetch only first commit if there is only one remote
        if len(remotes) == 1:
            vals.update({"defaults": {"depth": 1}})
        return vals
