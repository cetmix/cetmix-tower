# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Drop the unique (variable_id, jet_template_id) constraint.

    A Jet Template can now hold several values of the same variable,
    one per set of environments. Odoo does not drop constraints that are
    removed from `_sql_constraints`, so it must be dropped explicitly.
    """
    cr.execute(
        "ALTER TABLE cx_tower_variable_value "
        "DROP CONSTRAINT IF EXISTS "
        "cx_tower_variable_value_unique_variable_value_jet_template"
    )
    _logger.info(
        "Removed cx_tower_variable_value_unique_variable_value_jet_template"
        " constraint from cx_tower_variable_value"
    )
