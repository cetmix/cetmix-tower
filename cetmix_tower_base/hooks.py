# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)

# Xmlids that cetmix_tower_base now declares. They already exist under
# cetmix_tower_server on databases that had Tower installed.
XMLIDS_TO_BASE = (
    ("ir_module_category_tower", "ir.module.category"),
    ("ir_module_category_tower_server", "ir.module.category"),
    ("group_user", "res.groups"),
    ("group_manager", "res.groups"),
    ("group_root", "res.groups"),
    ("menu_root", "ir.ui.menu"),
    ("menu_cx_tower_log_root", "ir.ui.menu"),
    ("menu_settings", "ir.ui.menu"),
    ("menu_cetmix_tower_general_settings", "ir.ui.menu"),
    ("menu_cx_tower_tag", "ir.ui.menu"),
    ("action_cetmix_tower_config_settings", "ir.actions.act_window"),
    ("action_cx_tower_tag", "ir.actions.act_window"),
    ("cx_tower_tag_view_form", "ir.ui.view"),
    ("cx_tower_tag_view_tree", "ir.ui.view"),
    ("cx_tower_tag_search_view", "ir.ui.view"),
    ("rule_cx_tower_tag_user", "ir.rule"),
    ("rule_cx_tower_tag_manager", "ir.rule"),
    ("rule_cx_tower_tag_root", "ir.rule"),
    ("access_tag_user", "ir.model.access"),
    ("access_tag_manager", "ir.model.access"),
    ("access_tag_root", "ir.model.access"),
    ("access_cx_tower_vault_no_access", "ir.model.access"),
)


def _move_server_xmlids_to_base(cr):
    """Re-own xmlids that this module now declares.

    Run from ``pre_init_hook`` or a base pre-migration before XML loads.
    Server's update runs only after base is fully loaded, so a server
    pre-migration would be too late: base would create duplicate groups, menus and
    actions, and ``_process_end`` would delete the originals (and group
    membership). See task 5622 §8.1.

    Each UPDATE keeps ``res_id`` and ``noupdate``. The collision guard
    skips a row when ``cetmix_tower_base.<name>`` already exists, so the
    unique ``(module, name)`` index is preserved. The function is
    idempotent: a second run updates zero rows. On a fresh database it
    also updates zero rows.

    Args:
        cr (Cursor): Database cursor.

    Returns:
        int: Number of ``ir.model.data`` rows whose module was changed.
    """
    moved = 0
    for name, model in XMLIDS_TO_BASE:
        cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'cetmix_tower_base'
             WHERE module = 'cetmix_tower_server'
               AND name = %s
               AND model = %s
               AND NOT EXISTS (
                    SELECT 1
                      FROM ir_model_data AS other
                     WHERE other.module = 'cetmix_tower_base'
                       AND other.name = %s
               )
            """,
            (name, model, name),
        )
        moved += cr.rowcount
    _logger.info(
        "Moved %s ir.model.data row(s) from cetmix_tower_server to cetmix_tower_base",
        moved,
    )
    return moved


def pre_init_hook(env):
    """Re-own Tower xmlids before this module loads its data.

    Args:
        env (Environment): Odoo environment provided by the loader.
    """
    _move_server_xmlids_to_base(env.cr)
