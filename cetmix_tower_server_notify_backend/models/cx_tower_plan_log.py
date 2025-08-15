# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class CxTowerPlanLog(models.Model):
    _inherit = "cx.tower.plan.log"

    def _plan_finished(self):
        res = super()._plan_finished()

        # Use context timestamp to avoid timezone issues
        context_timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )

        # Action for button
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action.update(
            {
                "views": [(False, "form")],
            }
        )
        context = self.env.context.copy()
        params = dict(context.get("params") or {})
        params["button_name"] = _("View Log")
        context["params"] = params
        action["context"] = context

        for log in self:
            # don't notify if a plan that was run from another plan has been executed
            if log.parent_flight_plan_log_id:
                continue

            # Add record id to the action
            action.update(
                {
                    "res_id": log.id,
                }
            )

            # Send notification
            if log.plan_status == 0:
                log.create_uid.notify_success(
                    message=_(
                        "%(timestamp)s<br/>"
                        "Flight Plan '%(name)s' finished successfully",
                        name=log.plan_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=log.server_id.name,
                    sticky=True,
                    action=action,
                )
            else:
                log.create_uid.notify_danger(
                    message=_(
                        "%(timestamp)s<br/>"
                        "Flight Plan '%(name)s'"
                        " finished with error. "
                        "Please check the flight plan log for details.",
                        name=log.plan_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=log.server_id.name,
                    sticky=True,
                    action=action,
                )

        return res
