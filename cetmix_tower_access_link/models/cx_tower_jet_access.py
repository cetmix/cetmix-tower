import re
from odoo import api, fields, models

VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


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
            record.url_resolved = False
            record.is_url_valid = False
            if (
                not record.template_id
                or not record.jet_id
                or not record.template_id.url_code
            ):
                continue

            url = record.template_id.url_code
            has_error = False

            def replace_var(match):
                nonlocal has_error
                var_name = match.group(1)
                val = record.jet_id.get_variable_value(var_name)
                # If variable resolution explicitly fails (False or None)
                if val is False or val is None:
                    has_error = True
                    return "False"
                return str(val)

            # Resolve {{ variables }} using re.sub with callback for robustness
            resolved_url = VARIABLE_PATTERN.sub(replace_var, url)

            record.url_resolved = resolved_url
            record.is_url_valid = not has_error

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
