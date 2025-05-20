# Remove the "unique_variable_value_server" constraint for cx_tower_variable_value model
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove the unique_variable_value_server constraint before migration."""
    cr.execute(
        """
        ALTER TABLE cx_tower_variable_value
        DROP CONSTRAINT IF EXISTS unique_variable_value_server
        """
    )
    _logger.info(
        "Removed unique_variable_value_server constraint from cx_tower_variable_value"
    )
