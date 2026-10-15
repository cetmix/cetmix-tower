# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerDroneSkill(models.Model):
    """Kind of work a drone controller has reported.

    Records are created from a health reply. This module ships none.
    """

    _name = "cx.drone.skill"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _description = "Cetmix Tower Drone Skill"
    _order = "name"

    schema = fields.Json(
        readonly=True,
        help="Data and response schema reported by a controller for this skill",
    )
    schema_text = fields.Text(
        help="Data and response schema reported by a controller for this skill",
        compute="_compute_schema_text",
        groups="cetmix_tower_base.group_manager",
    )

    @api.depends("schema")
    def _compute_schema_text(self):
        """Show the stored schema as text.

        An empty schema stays empty. The text is the Python form of the
        stored object.

        Returns:
            None: The value is written on ``schema_text``.
        """
        for skill in self:
            skill.schema_text = str(skill.schema) if skill.schema else False

    def action_fetch_schema(self):
        """Load this skill's schema from its first linked controller.

        The controller is the linked one with the lowest priority, then
        the lowest id, including an inactive controller. Its status is
        not a reason to skip it. If that controller does not answer, the
        next one is not asked. With no linked controller, nothing is
        requested and the stored schema stays.

        Returns:
            dict: Notification. The form closes so it reloads.
        """
        self.ensure_one()
        controller_model = self.env["cx.drone.controller"]
        controller = controller_model.with_context(active_test=False).search(
            [("skill_ids", "in", self.id)], limit=1
        )
        if not controller:
            return controller_model._schema_fetch_notification(
                False,
                plural=False,
                message=self.env._("This skill is not linked to a controller."),
            )
        schemas = controller._read_skill_schemas()
        if schemas is None:
            return controller._schema_fetch_notification(False, plural=False)
        controller._apply_skill_schemas(schemas, self)
        return controller._schema_fetch_notification(True, plural=False)
