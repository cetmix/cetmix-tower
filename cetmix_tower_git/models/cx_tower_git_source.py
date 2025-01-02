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
        string="Remotes",
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
        # Update related files on create
        res._update_related_files()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Update related files on update
        self._update_related_files()
        return res

    def _update_related_files(self):
        # Update related files on update
        related_files = self.mapped("git_project_id").mapped("git_project_rel_ids")
        if related_files:
            related_files._save_to_file()

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
