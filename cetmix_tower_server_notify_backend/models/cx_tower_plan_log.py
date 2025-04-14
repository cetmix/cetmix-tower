# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class CxTowerPlanLog(models.Model):
    _inherit = "cx.tower.plan.log"

    def _plan_finished(self):
        res = super()._plan_finished()

        context_timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )
        for log in self:
            # don't notify if a plan that was runned from another plan has been executed
            if log.parent_flight_plan_log_id:
                continue

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
                )

        return res
