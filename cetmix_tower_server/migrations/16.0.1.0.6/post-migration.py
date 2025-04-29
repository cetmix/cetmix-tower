import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Generate references for files.
    """

    _logger.info("Starting reference generation for files.")
    env = api.Environment(cr, SUPERUSER_ID, {})
    model_obj = env["cx.tower.file"]
    records_without_reference = model_obj.search([("reference", "=", False)])
    for record in records_without_reference:
        record_reference = record._generate_or_fix_reference(record.name)
        record.write({"reference": record_reference})
        _logger.info(f"Generated reference for file {record.name}: {record_reference}")
    _logger.info("Reference generation for files completed.")
