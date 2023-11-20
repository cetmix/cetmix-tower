# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import ast

from odoo import fields, models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def _compute_file_count(self):
        """
        Compute total server files
        """
        for server in self:
            server.file_count = len(server.file_ids)

    file_ids = fields.One2many(
        "cx.tower.file",
        "server_id",
        string="Files",
    )
    file_count = fields.Integer(
        "Total Files",
        compute="_compute_file_count",
    )

    def action_open_files(self):
        """
        Open current server files
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_file.cx_tower_file_action"
        )
        action["domain"] = [("server_id", "=", self.id)]

        context = self._context.copy()
        if "context" in action and isinstance((action["context"]), str):
            context.update(ast.literal_eval(action["context"]))
        else:
            context.update(action.get("context", {}))

        context.update(
            {
                "default_server_id": self.id,
            }
        )
        action["context"] = context
        return action
