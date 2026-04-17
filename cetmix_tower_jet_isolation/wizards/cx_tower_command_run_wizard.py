from odoo import api, fields, models


class CxTowerCommandRunWizardFilter(models.TransientModel):
    _inherit = "cx.tower.command.run.wizard"

    is_isolated_context = fields.Boolean(compute="_compute_is_isolated_context")

    @api.depends("jet_ids")
    def _compute_is_isolated_context(self):
        for record in self:
            if record.jet_ids and any(
                j.jet_template_id.isolation_mode for j in record.jet_ids
            ):
                record.is_isolated_context = True
            else:
                record.is_isolated_context = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "default_jet_ids" in self.env.context:
            jet_ids = self.env["cx.tower.jet"].browse(
                self.env.context["default_jet_ids"]
            )
            if jet_ids:
                template = jet_ids[0].jet_template_id

                if template.isolation_mode:
                    if template.forced_applicability:
                        res["applicability"] = template.forced_applicability
                    if template.forced_command_tag_ids:
                        res["tag_ids"] = [(6, 0, template.forced_command_tag_ids.ids)]
        return res
