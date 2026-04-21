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
        jets = super().create(vals_list)
        for jet in jets:
            if jet.jet_template_id and jet.jet_template_id.access_template_ids:
                access_vals = []
                for template in jet.jet_template_id.access_template_ids:
                    access_vals.append(
                        (
                            0,
                            0,
                            {
                                "jet_id": jet.id,
                                "template_id": template.id,
                            },
                        )
                    )
                if access_vals:
                    jet.write({"access_ids": access_vals})
        return jets

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
