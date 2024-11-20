import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Populate the `reference` field for tables that belong to
    models inheriting from `cx.tower.reference.mixin`.
    This will copy the value from the `name` field to the
    `reference` field, but only for rows where `reference`
    is empty.
    """
    _logger.info("Starting SQL migration for reference field population.")

    # Step 1: Identify models that have a `reference` field
    # and belong to `cx.tower.reference.mixin` models
    env = api.Environment(cr, SUPERUSER_ID, {})
    mixin_registry = env.registry["cx.tower.reference.mixin"]
    for rec_model in env["ir.model"].search([]):
        model = env.get(rec_model.model, False)
        if isinstance(model, mixin_registry) and not model._abstract:
            records = model.search([("reference", "=", False)])
            for rec in records:
                rec.reference = rec.name
            _logger.info(f"Updated {len(records)} records in {rec_model.model}.")

    _logger.info("SQL migration completed successfully.")
