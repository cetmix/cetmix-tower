# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerJetTemplate(models.Model):
    _inherit = "cx.tower.jet.template"

    access_template_ids = fields.Many2many(
        comodel_name="cx.tower.access.template",
        relation="cx_tower_jet_template_access_rel",
        column1="jet_template_id",
        column2="access_template_id",
        string="Plantillas de Acceso",
        help="Plantillas de enlace pre-configuradas para los jets creados "
        "desde este template.",
    )
