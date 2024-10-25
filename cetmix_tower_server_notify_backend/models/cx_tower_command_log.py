# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class CxTowerCommandLog(models.Model):
    _inherit = "cx.tower.command.log"

    def _command_finished(self):
        res = super()._command_finished()
        context_timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )

        for rec in self:
            if rec.plan_log_id:  # type: ignore
                continue
            elif rec.command_status == 0:
                rec.create_uid.notify_success(
                    message=_(
                        "%(timestamp)s<br/>" "Command '%(name)s' finished successfully",
                        name=rec.command_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=rec.server_id.name,
                    sticky=True,
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
                )

        return res
