# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerJetMode(models.Model):
    _name = "cx.tower.jet.mode"
    _inherit = ["cx.tower.access.mixin"]
    _description = "Cetmix Tower Jet Mode"
    _order = "sequence, id"

    name = fields.Char(string="Mode Name", required=True)
    sequence = fields.Integer(default=10)
    description = fields.Html()
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        string="Jet Template",
        required=True,
        ondelete="cascade",
    )

    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_jet_mode_variable_rel",
        column1="mode_id",
        column2="variable_id",
        string="Configurations",
    )
    action_ids = fields.Many2many(
        comodel_name="cx.tower.jet.action",
        relation="cx_tower_jet_mode_action_rel",
        column1="mode_id",
        column2="action_id",
        string="Lifecycle Actions",
    )
    allowed_variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        compute="_compute_allowed_variable_ids",
        string="Allowed Variables",
    )

    @api.depends("jet_template_id", "jet_template_id.variable_value_ids")
    def _compute_allowed_variable_ids(self):
        for rec in self:
            if rec.jet_template_id:
                rec.allowed_variable_ids = (
                    rec.jet_template_id.variable_value_ids.variable_id
                )
            else:
                rec.allowed_variable_ids = self.env["cx.tower.variable"]
