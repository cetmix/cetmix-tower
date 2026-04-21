# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import re

from odoo import api, fields, models


class CxTowerJetAccess(models.Model):
    _name = "cx.tower.jet.access"
    _description = "Tower Jet Access"
    _order = "sequence, id"

    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        string="Jet",
        ondelete="cascade",
        required=True,
    )
    template_id = fields.Many2one(
        comodel_name="cx.tower.access.template",
        string="Link Template",
        required=True,
    )
    name = fields.Char(related="template_id.name", string="Name", readonly=True)
    sequence = fields.Integer(default=10)
    url_resolved = fields.Char(
        string="Link",
        compute="_compute_url_resolved",
    )
    is_url_valid = fields.Boolean(
        compute="_compute_url_resolved",
    )

    @api.depends("template_id", "jet_id")
    def _compute_url_resolved(self):
        for record in self:
            if not record.template_id or not record.jet_id:
                record.url_resolved = False
                continue

            url = record.template_id.url_code
            if not url:
                record.url_resolved = False
                continue

            # Resolve {{ variables }} using jet.get_variable_value
            variables = re.findall(r"\{\{\s*(\w+)\s*\}\}", url)
            for var in variables:
                val = record.jet_id.get_variable_value(var)
                if val is None:
                    val = ""
                placeholder = f"{{{{ {var} }}}}"
                url = url.replace(placeholder, str(val))
                placeholder_no_space = f"{{{{{var}}}}}"
                url = url.replace(placeholder_no_space, str(val))

            # Check if any resolved variable is 'False'
            record.url_resolved = url
            record.is_url_valid = bool(url and "False" not in url)

    def action_open_url(self):
        """Action to open the resolved URL in a new tab."""
        self.ensure_one()
        if self.url_resolved:
            return {
                "type": "ir.actions.act_url",
                "url": self.url_resolved,
                "target": "new",
            }
        return False
