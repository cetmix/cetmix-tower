# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerDroneController(models.Model):
    _inherit = "cx.tower.drone.controller"

    drone_command_log_count = fields.Integer(
        string="Commands",
        compute="_compute_drone_command_log_count",
        help="Tower command logs executed on this controller via a drone job",
    )

    def _compute_drone_command_log_count(self):
        counts = dict(
            self.env["cx.tower.command.log"]
            .sudo()
            ._read_group(
                [("drone_controller_id", "in", self.ids)],
                ["drone_controller_id"],
                ["__count"],
            )
        )
        for controller in self:
            controller.drone_command_log_count = counts.get(controller, 0)

    def action_view_command_logs(self):
        """Open command logs run on this controller.

        Returns:
            dict: Window action on ``cx.tower.command.log``.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("drone_controller_id", "=", self.id)]
        return action
