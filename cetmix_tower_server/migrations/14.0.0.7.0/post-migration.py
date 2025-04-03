import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Replace 'COMMAND_RESULT' with 'result' in command 'code' field.
    """

    _logger.warning("-== Migration started ==-")

    # Update command status values to new constants
    cr.execute(
        """
        UPDATE cx_tower_command
        SET code = REPLACE(code, 'COMMAND_RESULT', 'result')
        WHERE code LIKE '%COMMAND_RESULT%'
    """
    )

    _logger.warning("-== Migration completed ==-")
