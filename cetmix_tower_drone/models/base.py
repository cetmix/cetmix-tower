# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class Base(models.AbstractModel):
    """Add drone dispatch to every model, like ``with_delay()`` of queue_job."""

    _inherit = "base"

    def launch_drone(self, skill, on_complete, payload, drone_timeout=0):
        """Dispatch a job to a drone and return it.

        The caller builds ``payload``. This module encrypts it and sends
        it; it does not know how to build one.

        Args:
            skill (str): Skill reference reported by a controller.
            on_complete (method): Bound method of a recordset, or of the
                model when the recordset has no ids. Called on every
                terminal outcome. Signature: ``(drone_job, result)``.
            payload (dict): JSON object sent as ``data``. In memory only,
                never stored.
            drone_timeout (int): Seconds without a heartbeat. ``0`` means
                no timeout. Defaults to ``0``. Named so it is not taken
                for an SSH or request timeout.

        Returns:
            cx.tower.drone.job: A reserved job in state ``pending`` (one
                record), or an empty recordset when no controller was a
                candidate. A returned job has NOT been submitted yet: the
                POST happens after this transaction commits.

        Raises:
            ValidationError: If the callback, payload or drone timeout is
                not valid. Nothing is reserved or created in that case.
        """
        job = self.env["cx.tower.drone.job"]._launch(
            skill, on_complete, payload, drone_timeout
        )
        return self.env["cx.tower.drone.job"].browse(job.ids)
