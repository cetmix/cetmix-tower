# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerJetWaypointTemplate(models.Model):
    _name = "cx.tower.jet.waypoint.template"
    _inherit = [
        "cx.tower.jet.waypoint.template",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "sequence",
            "access_level",
            "jet_template_id",
            "plan_create_id",
            "plan_arrive_id",
            "plan_leave_id",
            "plan_delete_id",
            "note",
        ]
        return res

    def _get_deferred_m2o_import_fields(self):
        """Return m2o waypoint-template fields resolved after import."""
        return {
            "jet_template_id": "cx.tower.jet.template",
        }
