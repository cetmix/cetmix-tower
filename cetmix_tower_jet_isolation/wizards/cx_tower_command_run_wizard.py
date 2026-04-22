from odoo import api, fields, models


class CxTowerCommandRunWizard(models.TransientModel):
    _inherit = "cx.tower.command.run.wizard"

    is_restricted_context = fields.Boolean(compute="_compute_is_restricted_context")
    isolated_tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        compute="_compute_isolated_tag_ids",
        string="Forced Tags",
    )

    @api.depends("jet_ids.jet_template_id.isolation_mode")
    def _compute_is_restricted_context(self):
        is_global_manager = self.env.user.has_group("cetmix_tower_server.group_manager")
        for record in self:
            jets = record.jet_ids or self.env["cx.tower.jet"].browse(
                self.env.context.get("default_jet_ids", [])
            )

            is_isolated = any(j.jet_template_id.isolation_mode for j in jets)

            if is_global_manager:
                is_manager = True
            elif jets and all(self.env.user in j.manager_ids for j in jets):
                is_manager = True
            else:
                is_manager = False

            record.is_restricted_context = is_isolated and not is_manager

    @api.depends("tag_ids")
    def _compute_isolated_tag_ids(self):
        for record in self:
            record.isolated_tag_ids = record.tag_ids

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "default_jet_ids" in self.env.context:
            jet_ids = self.env["cx.tower.jet"].browse(
                self.env.context["default_jet_ids"]
            )
            # Find the first jet that has isolation mode enabled
            isolated_jet = jet_ids.filtered(lambda j: j.jet_template_id.isolation_mode)[
                :1
            ]
            if isolated_jet:
                template = isolated_jet.jet_template_id
                if template.forced_applicability:
                    res["applicability"] = template.forced_applicability
                if template.forced_command_tag_ids:
                    res["tag_ids"] = [(6, 0, template.forced_command_tag_ids.ids)]
        return res
