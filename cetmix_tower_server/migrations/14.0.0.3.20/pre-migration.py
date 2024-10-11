import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Update cx_tower_variable_value table"""
    _logger.warning("-== Migration started ==-")

    query = """
    DO $$
        BEGIN
        IF EXISTS(SELECT *
            FROM information_schema.columns
            WHERE table_name='cx_tower_variable_value' and column_name='action_id' )
        THEN
            ALTER TABLE cx_tower_variable_value RENAME COLUMN
                action_id TO plan_line_action_id;
        END IF;
    END $$;
    """
    cr.execute(query)
