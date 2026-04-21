import re

from odoo import api, fields, models

VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


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

    def _get_url_variables(self):
        self.ensure_one()
        if not self.url_code:
            return []
        return VARIABLE_PATTERN.findall(self.url_code)

    @api.depends("url_code")
    def _compute_variable_ids(self):
        for record in self:
            refs = record._get_url_variables()
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
            variables = record._get_url_variables()
            if variables:
                unique_vars = sorted(list(set(variables)))
                record.required_variables = ", ".join(unique_vars)
            else:
                record.required_variables = False
