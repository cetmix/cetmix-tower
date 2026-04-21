# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import re

from odoo import api, fields, models


class CxTowerAccessTemplate(models.Model):
    _name = "cx.tower.access.template"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.tag.mixin",
        "cx.tower.access.mixin",
        "cx.tower.access.role.mixin",
    ]
    _description = "Tower Access Template"
    _order = "name"

    active = fields.Boolean(default=True)
    description = fields.Text()
    url_code = fields.Text(
        required=True,
        help="URL or fixed part, supports {{ variable }} syntax",
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        string="Variables",
        compute="_compute_variable_ids",
        help="Tower variables detected in the URL",
    )
    required_variables = fields.Char(
        compute="_compute_required_variables",
        store=True,
        help="Automatically parsed from the URL",
    )

    # Access Role relations
    user_ids = fields.Many2many(
        relation="cx_tower_access_template_user_rel",
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_access_template_manager_rel",
    )

    @api.depends("url_code")
    def _compute_variable_ids(self):
        for record in self:
            if not record.url_code:
                record.variable_ids = [(5, 0, 0)]
                continue

            # Find all {{ var }} patterns
            refs = re.findall(r"\{\{\s*(\w+)\s*\}\}", record.url_code)
            if not refs:
                record.variable_ids = [(5, 0, 0)]
                continue

            # Search for variables in the system
            tower_vars = self.env["cx.tower.variable"].search(
                [("reference", "in", list(set(refs)))]
            )
            record.variable_ids = [(6, 0, tower_vars.ids)]

    @api.depends("url_code")
    def _compute_required_variables(self):
        for record in self:
            if record.url_code:
                variables = re.findall(r"\{\{\s*(\w+)\s*\}\}", record.url_code)
                unique_vars = sorted(list(set(variables)))
                record.required_variables = ", ".join(unique_vars)
            else:
                record.required_variables = False
