# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

from .constants import (
    NO_CONTROLLER_POLICY_FAIL,
    NO_CONTROLLER_POLICY_FALLBACK,
    NO_CONTROLLER_POLICY_PARAM,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cetmix_tower_drone_ssh_no_controller_policy = fields.Selection(
        string="No Drone Controller",
        selection=[
            (NO_CONTROLLER_POLICY_FAIL, "Fail"),
            (NO_CONTROLLER_POLICY_FALLBACK, "Fallback"),
        ],
        default=NO_CONTROLLER_POLICY_FAIL,
        config_parameter=NO_CONTROLLER_POLICY_PARAM,
        help="What to do with an SSH command when no drone controller is "
        "available. Fail: finish the command with an error. Fallback: run "
        "the command without a drone.",
    )
