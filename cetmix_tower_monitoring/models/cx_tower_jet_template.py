# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJetTemplate(models.Model):
    _inherit = "cx.tower.jet.template"

    metric_ids = fields.One2many(
        comodel_name="cx.tower.jet.template.metric",
        inverse_name="jet_template_id",
        string="Metrics",
        copy=True,
        groups="cetmix_tower_base.group_manager",
        yaml_export="explode",
        help="Jets of this template get these metrics",
    )
