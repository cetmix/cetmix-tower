# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    access_ids = fields.One2many(
        comodel_name="cx.tower.jet.access",
        inverse_name="jet_id",
        string="Quick Access Links",
        help="Quick access links configured for this jet.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("jet_template_id") and not vals.get("access_ids"):
                jet_template = self.env["cx.tower.jet.template"].browse(
                    vals["jet_template_id"]
                )
                if jet_template.access_template_ids:
                    access_vals = [
                        (0, 0, {"template_id": t.id})
                        for t in jet_template.access_template_ids
                    ]
                    vals["access_ids"] = access_vals
        return super().create(vals_list)

    def action_sync_access_links(self):
        """Sync access links from the jet template that are not yet in the jet."""
        self.ensure_one()
        if not self.jet_template_id:
            return

        existing_template_ids = self.access_ids.mapped("template_id").ids
        new_templates = self.jet_template_id.access_template_ids.filtered(
            lambda t: t.id not in existing_template_ids
        )

        if new_templates:
            access_vals = []
            for template in new_templates:
                access_vals.append(
                    (
                        0,
                        0,
                        {
                            "jet_id": self.id,
                            "template_id": template.id,
                        },
                    )
                )
            self.write({"access_ids": access_vals})
