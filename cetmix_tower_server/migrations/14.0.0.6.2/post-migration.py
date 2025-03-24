import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Force compute many2many computed fields.
    """

    _logger.warning("-== Migration started ==-")
    _logger.info("Command log: update 'command_status' field.")

    # Update command status values to new constants
    cr.execute(
        """
        UPDATE cx_tower_command_log
        SET command_status = CASE
            WHEN command_status = -1 THEN -100  -- GENERAL_ERROR
            WHEN command_status = -2 THEN -101  -- NOT_FOUND
            WHEN command_status = -5 THEN -201  -- ANOTHER_COMMAND_RUNNING
            WHEN command_status = -6 THEN -202  -- NO_COMMAND_RUNNER_FOUND
            WHEN command_status = -24 THEN -203 -- PYTHON_COMMAND_ERROR
            WHEN command_status = -20 THEN -205 -- PLAN_LINE_CONDITION_CHECK_FAILED
            ELSE command_status
        END
        WHERE command_status IN (-1, -2, -5, -6, -20, -24)
    """
    )

    _logger.info("Flight plan: update 'plan_status' field.")

    # Update plan status values to new constants
    cr.execute(
        """
        UPDATE cx_tower_plan_log
        SET plan_status = CASE
            WHEN plan_status = -7 THEN -301  -- ANOTHER_PLAN_RUNNING
            WHEN plan_status = -1 THEN -302  -- PLAN_IS_EMPTY
            WHEN plan_status = -10 THEN -303 -- PLAN_NOT_ASSIGNED
            WHEN plan_status = -11 THEN -304 -- PLAN_LINE_NOT_ASSIGNED
            ELSE plan_status
        END
        WHERE plan_status IN (-7, -1, -10, -11)
    """
    )

    _logger.warning("-== Migration completed ==-")
