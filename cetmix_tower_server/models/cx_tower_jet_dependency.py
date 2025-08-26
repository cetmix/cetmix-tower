# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJetDependency(models.Model):
    """Model to manage dependent Jets"""

    _name = "cx.tower.jet.dependency"
    _description = "Cetmix Tower Jet Dependency"
    _log_access = False

    jet_template_dependency_id = fields.Many2one(
        comodel_name="cx.tower.jet.template.dependency",
        string="Jet Template Dependency",
        help="Related jet template dependency. "
        "Used to track dependency changes at the template level.",
        ondelete="cascade",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        string="Jet",
        required=True,
        help="Jet this dependence belongs to.",
        ondelete="cascade",
    )
    jet_depends_on_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        string="Depends On",
        required=True,
        help="Jet this Jet depends on.",
        ondelete="cascade",
    )
