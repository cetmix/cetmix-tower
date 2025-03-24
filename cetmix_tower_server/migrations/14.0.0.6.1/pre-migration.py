import logging

from psycopg2.extensions import AsIs

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Delete obsolete wizard tables.
    Rename plan-tag relation table and its columns
    if destination doesn't exist.

    Parameters:
        cr (cursor): Database cursor
        version (str): Module version
    """
    _logger.warning("-== Migration started ==-")

    # -- 1 --
    # Rename plan-tag relation table and columns
    # if destination doesn't exist
    cr.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'cx_tower_plan_cx_tower_tag_rel'
            ) AND NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'cx_tower_plan_tag_rel'
            ) THEN
                ALTER TABLE cx_tower_plan_cx_tower_tag_rel
                RENAME TO cx_tower_plan_tag_rel;

                ALTER TABLE cx_tower_plan_tag_rel
                RENAME COLUMN cx_tower_plan_id TO plan_id;

                ALTER TABLE cx_tower_plan_tag_rel
                RENAME COLUMN cx_tower_tag_id TO tag_id;
            END IF;
        END $$;
        """
    )

    # -- 2 --
    # Delete obsolete wizard tables
    # List of tables to delete
    tables_to_delete = [
        "cx_tower_command_execute_wizard",
        "cx_tower_command_execute_wizard_cx_tower_server_rel",
        "cx_tower_command_execute_wizard_cx_tower_variable_rel",
        "cx_tower_plan_execute_wizard",
        "cx_tower_plan_execute_tag_rel",
        "cx_tower_plan_execute_wizard_cx_tower_server_rel",
    ]

    # Drop tables if they exist
    for table in tables_to_delete:
        cr.execute(
            """
            DROP TABLE IF EXISTS %s CASCADE
            """,
            (AsIs(table),),
        )
    _logger.warning("-== Migration completed ==-")
