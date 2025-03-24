import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Set default value for `skip_host_key` field to `True`
    for all existing servers.
    """
    _logger.info("Starting migration for `skip_host_key` field.")
    env = api.Environment(cr, SUPERUSER_ID, {})
    servers = env["cx.tower.server"].search([("host_key", "=", False)])
    servers.write(
        {
            "skip_host_key": True,
        }
    )
    _logger.info("Migration for `skip_host_key` field completed.")
