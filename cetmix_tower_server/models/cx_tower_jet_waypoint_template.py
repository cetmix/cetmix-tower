# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerJetWaypointTemplate(models.Model):
    """Jet Waypoint Templates define waypoints for jet templates"""

    _name = "cx.tower.jet.waypoint.template"
    _description = "Cetmix Tower Jet Waypoint Template"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.access.mixin"]
    _order = "sequence, name asc"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10, help="Used to sort waypoints in views")
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        ondelete="cascade",
        help="Jet template this waypoint template belongs to",
    )
    plan_create_id = fields.Many2one(
        string="Create Flight Plan",
        comodel_name="cx.tower.plan",
        help="Flight plan to run after waypoint is created",
    )
    plan_arrive_id = fields.Many2one(
        string="Arrive Flight Plan",
        comodel_name="cx.tower.plan",
        help="Flight plan to run after waypoint is reached",
    )
    plan_leave_id = fields.Many2one(
        string="Leave Flight Plan",
        comodel_name="cx.tower.plan",
        help="Flight plan to run before leaving the waypoint",
    )
    plan_delete_id = fields.Many2one(
        string="Delete Flight Plan",
        comodel_name="cx.tower.plan",
        help="Flight plan to run before deleting the waypoint",
    )
    note = fields.Text()

    def _selection_access_level(self):
        """
        Available access levels

        Returns:
            List of tuples: available options.
        """
        return [
            ("2", "Manager"),
            ("3", "Root"),
        ]

    @api.depends("name", "jet_template_id", "jet_template_id.name")
    def _compute_display_name(self):
        """Compute record display name.

        The UI should show waypoint templates in the format:
        ``<name> (<jet_template_name>)``.
        """
        for record in self:
            jet_template_name = record.jet_template_id.name or ""  # type: ignore[attr-defined]
            if jet_template_name:
                record.display_name = (  # type: ignore[attr-defined]
                    f"{record.name} ({jet_template_name})"
                )
            else:
                record.display_name = record.name  # type: ignore[attr-defined]
