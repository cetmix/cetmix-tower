# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerCommand(models.Model):
    _name = "cx.tower.command"
    _inherit = ["cx.tower.command", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "access_level",
            "name",
            "action",
            "allow_parallel_run",
            "note",
            "os_ids",
            "tag_ids",
            "path",
            "file_template_id",
            "if_file_exists",
            "disconnect_file",
            "flight_plan_id",
            "jet_template_id",
            "jet_action_id",
            "waypoint_template_id",
            "fly_here",
            "code",
            "no_split_for_sudo",
            "server_status",
            "variable_ids",
            "secret_ids",
        ]
        return res

    def _get_deferred_m2o_import_fields(self):
        """Return m2o command fields resolved after the main import pass."""
        return {
            "jet_template_id": "cx.tower.jet.template",
            "jet_action_id": "cx.tower.jet.action",
            "waypoint_template_id": "cx.tower.jet.waypoint.template",
        }
