# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerJetTemplate(models.Model):
    _inherit = "cx.tower.jet.template"

    backup_template_ids = fields.One2many(
        "cx.tower.backup.template",
        "jet_template_id",
        groups="cetmix_tower_base.group_root",
        yaml_export="explode",
    )
