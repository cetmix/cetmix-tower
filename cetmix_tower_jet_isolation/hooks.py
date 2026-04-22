def uninstall_hook(env):
    """Reset isolation fields on all jet templates when the module is uninstalled.

    Odoo does not drop columns when a module is uninstalled, so any templates
    that had ``isolation_mode`` enabled would still carry the value ``True``
    in their row.  When the module is re-installed (or the column is somehow
    still read) those stale values would silently reactivate the restriction
    logic.  Resetting them here ensures a clean state.
    """
    env["cx.tower.jet.template"].with_context(active_test=False).search([]).write(
        {
            "isolation_mode": False,
            "forced_applicability": False,
            "forced_command_tag_ids": [(5,)],
            "forced_plan_tag_ids": [(5,)],
        }
    )
