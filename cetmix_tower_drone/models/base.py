# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class Base(models.AbstractModel):
    """Add drone dispatch to every model, like ``with_delay()`` of queue_job."""

    _inherit = "base"

    def launch_drone(self, tower_drone_skill, tower_drone_on_complete, **params):
        """Dispatch a job to a drone and return it.

        The two job arguments carry the ``tower_drone_`` prefix so that a
        skill may name its own params freely.

        Args:
            tower_drone_skill (str): Skill code, a key of
                ``_get_drone_skills()``.
            tower_drone_on_complete (method): Bound method called on every
                terminal outcome. Signature: ``(drone_job, result)``.
            **params: Skill parameters. In-memory only, never stored.

        Returns:
            cx.tower.drone.job: A reserved job in state ``pending`` (one
                record), or an empty recordset when no controller was a
                candidate. A returned job has NOT been submitted yet: the
                POST happens after this transaction commits.
        """
        job = self.env["cx.tower.drone.job"]._launch(
            tower_drone_skill, tower_drone_on_complete, params
        )
        return self.env["cx.tower.drone.job"].browse(job.ids)

    def get_drone_skills(self):
        """Return the skill codes this database can dispatch.

        Returns:
            list: Sorted skill codes from ``_get_drone_skills()``.
        """
        return sorted(self.env["cx.tower.drone.job"]._get_drone_skills())
