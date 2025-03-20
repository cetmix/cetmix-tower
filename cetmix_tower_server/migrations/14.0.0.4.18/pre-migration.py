import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Prepare database for host key functionality by removing old field selections.

    This migration removes selection values for the 'use_sudo' field in the command
    execution wizard, which is necessary before adding the new host key functionality.

    Parameters:
        cr (cursor): Database cursor
        version (str): Module version
    """
    _logger.warning("-== Migration started ==-")

    # Delete old selection field data from ir_model_fields_selection
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
        WHERE field_id IN (
            SELECT id FROM ir_model_fields
            WHERE name = 'use_sudo'
            AND model = 'cx.tower.command.execute.wizard'
        );
    """
    )
