# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CxTowerDroneSkill(models.Model):
    """Kind of work a drone controller accepts.

    The behaviour of a skill is registered in
    ``cx.tower.drone.job._get_drone_skills()``; this record is what
    controllers point to.
    """

    _name = "cx.tower.drone.skill"
    _description = "Cetmix Tower Drone Skill"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)

    _sql_constraints = [
        ("code_unique", "UNIQUE(code)", "Skill code must be unique"),
    ]

    @api.constrains("code")
    def _check_code(self):
        """The code must be registered in ``_get_drone_skills()``."""
        skills = self.env["cx.tower.drone.job"]._get_drone_skills()
        for skill in self:
            if skill.code not in skills:
                raise ValidationError(
                    self.env._(
                        "Skill code '%(code)s' is not registered. "
                        "Available skills: %(skills)s",
                        code=skill.code,
                        skills=", ".join(sorted(skills)) or self.env._("none"),
                    )
                )
