# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerJetTemplate(models.Model):
    _name = "cx.tower.jet.template"
    _inherit = [
        "cx.tower.jet.template",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "note",
            "tag_ids",
            "limit_per_server",
            "show_in_create_wizard",
            "plan_install_id",
            "plan_uninstall_id",
            "plan_clone_same_server_id",
            "plan_clone_different_server_id",
            "variable_value_ids",
            "action_ids",
            # "action_create_id",  # TODO
            # "action_destroy_id",
            "server_log_ids",
            "template_requires_ids",
            "scheduled_task_ids",
        ]
        return res
