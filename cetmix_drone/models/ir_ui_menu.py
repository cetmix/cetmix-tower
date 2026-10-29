# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models

DRONE_ROOT_MENU_ICON = "cetmix_drone,static/description/icon.png"


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _cetmix_drone_set_root_menu_name(self):
        """Name the root menu Drone unless Cetmix Tower Server is installed.

        ``cetmix_tower_base`` creates ``menu_root`` as Cetmix Tower, and
        reloads that name on every update of base. This runs from this
        module's data and again after translations are loaded. It writes
        Drone only while ``cetmix_tower_server`` is not installed and is
        not about to load in this same update. A drone update does not
        load server, so an unconditional name would replace Cetmix Tower.
        While server is ``to install`` or ``to upgrade``, server's own
        data still runs afterwards and keeps Cetmix Tower.

        The name is translated. Assigning it would update only the
        language of this call, and leave the translations of Cetmix Tower
        that belong to ``cetmix_tower_base.menu_root``. Every installed
        language is set to Drone, using that language's translation.
        The root menu icon is set to this module's icon. ``web_icon`` is
        not translated; writing it also loads the image.

        Returns:
            None
        """
        server = self.env["ir.module.module"].search(
            [("name", "=", "cetmix_tower_server")], limit=1
        )
        if server.state in ("installed", "to upgrade", "to install"):
            return
        menu = self.env.ref("cetmix_tower_base.menu_root")
        translations = {"en_US": "Drone"}
        for code, _label in self.env["res.lang"].get_installed():
            if code != "en_US":
                translations[code] = self.with_context(lang=code).env._("Drone")
        menu.update_field_translations("name", translations)
        menu.web_icon = DRONE_ROOT_MENU_ICON
