import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Force compute many2many computed fields.
    """

    # `command_ids` for flight plans.
    _logger.info("Starting migration for flight plan `command_ids` field.")
    env = api.Environment(cr, SUPERUSER_ID, {})
    model_obj = env["cx.tower.plan"]
    env.add_to_compute(model_obj._fields["command_ids"], model_obj.search([]))
    model_obj.recompute()
    _logger.info("Migration for flight plan `command_ids` field completed.")

    _logger.info("Starting migration for `variable_ids` field.")

    # `variable_value_ids` for `cx.tower.variable.value` model.
    model_obj = env["cx.tower.variable.value"]
    env.add_to_compute(model_obj._fields["variable_ids"], model_obj.search([]))
    model_obj.recompute()

    # `variable_value_ids` and `secret_ids` for other models.
    for model in ["cx.tower.command", "cx.tower.file", "cx.tower.file.template"]:
        model_obj = env[model]
        env.add_to_compute(model_obj._fields["variable_ids"], model_obj.search([]))
        env.add_to_compute(model_obj._fields["secret_ids"], model_obj.search([]))
        model_obj.recompute()
        _logger.info(
            f"Migration for {model} `variable_ids` and `secret_ids` fields completed."
        )
