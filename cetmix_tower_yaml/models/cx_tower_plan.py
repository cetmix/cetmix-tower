# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerPlan(models.Model):
    _name = "cx.tower.plan"
    _inherit = ["cx.tower.plan", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "access_level",
            "allow_parallel_run",
            "color",
            "tag_ids",
            "note",
            "on_error_action",
            "custom_exit_code",
            "line_ids",
        ]
        return res

    def _get_deferred_x2m_import_fields(self):
        """Defer plan lines whose command is not resolvable during nested import.

        Deep YAML (e.g. a command's waypoint inlines a jet template whose plans
        reference that same command) creates a forward reference: plan lines are
        prepared before the command exists in the database. Queue those lines
        and create them after the main import pass when ``command_id`` can be
        resolved.
        """
        return {
            "line_ids": {
                "child_model": "cx.tower.plan.line",
                "deferred_field": "command_id",
                "target_model": "cx.tower.command",
            }
        }
