# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
from odoo import models


class QueueJob(models.Model):
    _inherit = "queue.job"

    QUEUE_JOB_ERROR = 601

    def write(self, vals):
        """
        Override write method to update command status
        and write error information in the log record
        """
        if vals.get("state") == "failed":
            log_record = self.kwargs.get("log_record")
            if log_record:
                log_record.finish(
                    status=self.QUEUE_JOB_ERROR,
                    error=vals.get("exc_info"),
                )
        return super().write(vals)
