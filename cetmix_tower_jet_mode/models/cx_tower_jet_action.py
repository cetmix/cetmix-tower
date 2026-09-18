# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerJetAction(models.Model):
    _inherit = "cx.tower.jet.action"

    is_mode_allowed = fields.Boolean(
        compute="_compute_is_mode_allowed",
        store=False,
    )

    @api.depends(
        "jet_template_id.active_mode_id",
        "jet_template_id.active_mode_id.action_ids",
    )
    def _compute_is_mode_allowed(self):
        for rec in self:
            active_mode = False
            if rec.jet_template_id:
                active_mode = rec.jet_template_id.active_mode_id

            if not active_mode:
                rec.is_mode_allowed = True
            else:
                rec.is_mode_allowed = rec.id in active_mode.action_ids.ids

    @api.model
    def web_search_read(self, domain=None, *args, **kwargs):  # noqa: C901
        if domain:
            # 1. Handle domain when loading One2many relation (contains list of IDs)
            record_ids = []
            for arg in domain:
                if isinstance(arg, list | tuple) and len(arg) == 3:
                    field, op, val = arg
                    if field == "id" and op == "in" and isinstance(val, list):
                        record_ids.extend(val)
                    elif field == "id" and op == "=" and isinstance(val, int):
                        record_ids.append(val)

            if record_ids:
                records = self.browse(record_ids).exists()
                filtered_ids = []
                for rec in records:
                    if rec.jet_template_id:
                        if rec.jet_template_id.active_mode_id:
                            if (
                                rec.id
                                in rec.jet_template_id.active_mode_id.action_ids.ids
                            ):
                                filtered_ids.append(rec.id)
                        else:
                            filtered_ids.append(rec.id)
                    else:
                        filtered_ids.append(rec.id)

                new_domain = []
                for arg in domain:
                    if (
                        isinstance(arg, list | tuple)
                        and len(arg) == 3
                        and arg[0] == "id"
                        and arg[1] in ("in", "=")
                    ):
                        new_domain.append(("id", "in", filtered_ids))
                    else:
                        new_domain.append(arg)
                domain = new_domain

            # 2. Handle generic domain with parent template field constraints
            template_id = False
            for arg in domain:
                if isinstance(arg, list | tuple) and len(arg) == 3:
                    field, op, val = arg
                    if field == "jet_template_id" and op == "=" and val:
                        template_id = val

            if template_id:
                template = self.env["cx.tower.jet.template"].browse(template_id)
                if template.exists() and template.active_mode_id:
                    mode_ids = template.active_mode_id.action_ids.ids
                    domain = domain + [("id", "in", mode_ids)]

        return super().web_search_read(domain, *args, **kwargs)
