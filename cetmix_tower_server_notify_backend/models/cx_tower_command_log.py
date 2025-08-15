# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class CxTowerCommandLog(models.Model):
    _inherit = "cx.tower.command.log"

    def _command_finished(self):
        res = super()._command_finished()

        # Use context timestamp to avoid timezone issues
        context_timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )

        # Action for button
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
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

        for rec in self:
            # Record might be deleted before we get here.
            # Eg in case Flight Plan is run on server deletion.
            #
            # Also do not send notification if command is run
            # from a Flight Plan.
            if not rec.exists() or rec.plan_log_id:  # type: ignore
                continue

            # Add record id to the action
            action.update(
                {
                    "res_id": rec.id,
                }
            )

            # Send notification
            if rec.command_status == 0:
                rec.create_uid.notify_success(
                    message=_(
                        "%(timestamp)s<br/>" "Command '%(name)s' finished successfully",
                        name=rec.command_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=rec.server_id.name,
                    sticky=True,
                    action=action,
                )
            else:
                rec.create_uid.notify_danger(
                    message=_(
                        "%(timestamp)s<br/>"
                        "Command '%(name)s'"
                        " finished with error. "
                        "Please check the command log for details.",
                        name=rec.command_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=rec.server_id.name,
                    sticky=True,
                    action=action,
                )

        return res
