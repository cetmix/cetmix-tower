# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.cetmix_tower_base.hooks import _move_server_xmlids_to_base


def migrate(cr, version):
    """Preserve the Logs menu and its children when moving ownership to base.

    Args:
        cr (Cursor): Database cursor.
        version (str): Previously installed module version.
    """
    _move_server_xmlids_to_base(cr)
