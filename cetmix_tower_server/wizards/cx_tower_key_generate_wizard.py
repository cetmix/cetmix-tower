# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerKeyGenerateWizard(models.TransientModel):
    """Choose the type of a new SSH key and generate it"""

    _name = "cx.tower.key.generate.wizard"
    _description = "Cetmix Tower Generate SSH Key"

    key_id = fields.Many2one(
        comodel_name="cx.tower.key",
        required=True,
        ondelete="cascade",
    )
    key_type = fields.Selection(
        selection=[
            ("ed25519", "Ed25519"),
            ("ecdsa", "ECDSA (nistp256)"),
            ("rsa", "RSA (4096 bit)"),
        ],
        required=True,
        default="ed25519",
        help="Algorithm of the new SSH key",
    )
    overwrite = fields.Boolean(
        help="Replace the existing private key",
    )

    def action_generate_ssh_key(self):
        """Generate the SSH key and close the wizard"""
        self.ensure_one()
        self.key_id._generate_ssh_key(key_type=self.key_type, overwrite=self.overwrite)
        return {"type": "ir.actions.act_window_close"}
