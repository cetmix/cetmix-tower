import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Prepare database for host key functionality by removing old field selections.

    This migration removes selection values for the 'applicability' field in the command
    and flight plan execution wizards, which is necessary before renaming the models.

    Parameters:
        cr (cursor): Database cursor
        version (str): Module version
    """
    _logger.warning("-== Migration started ==-")

    # Command execution wizard
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
        WHERE field_id IN (
            SELECT id FROM ir_model_fields
            WHERE name in ('applicability', 'action')
            AND model = 'cx.tower.command.execute.wizard'
        );
    """
    )
    # Flight plan execution wizard
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
        WHERE field_id IN (
            SELECT id FROM ir_model_fields
            WHERE name = 'applicability'
            AND model = 'cx.tower.plan.execute.wizard'
        );
    """
    )
    _logger.warning("-== Migration completed ==-")
