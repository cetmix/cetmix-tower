from odoo import api, fields, models


class CxTowerPlanRunWizardFilter(models.TransientModel):
    _inherit = "cx.tower.plan.run.wizard"

    is_restricted_context = fields.Boolean(compute="_compute_is_restricted_context")

    @api.depends("jet_ids")
    def _compute_is_restricted_context(self):
        is_global_manager = self.env.user.has_group("cetmix_tower_server.group_manager")
        for record in self:
            jets = record.jet_ids or self.env["cx.tower.jet"].browse(
                self.env.context.get("default_jet_ids", [])
            )

            is_isolated = bool(
                jets and any(j.jet_template_id.isolation_mode for j in jets)
            )

            if is_global_manager:
                is_manager = True
            elif jets and all(self.env.user in j.manager_ids for j in jets):
                is_manager = True
            else:
                is_manager = False

            record.is_restricted_context = is_isolated and not is_manager

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
                    if template.forced_plan_tag_ids:
                        res["tag_ids"] = [(6, 0, template.forced_plan_tag_ids.ids)]
        return res
