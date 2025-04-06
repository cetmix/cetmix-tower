import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        f"Starting post-migration for "
        f"ssh_port field from Char to Integer in version {version}."
    )

    models = ["cx_tower_server_template", "cx_tower_server"]

    for model in models:
        _logger.info("Processing model: %s", model)

        query = sql.SQL(
            """
            ALTER TABLE {table}
            ALTER COLUMN {column} TYPE INTEGER USING {moved_column}::INTEGER;
            ALTER TABLE {table} DROP COLUMN IF EXISTS {moved_column};
        """
        ).format(
            table=sql.Identifier(model),
            column=sql.Identifier("ssh_port"),
            moved_column=sql.Identifier("ssh_port_moved0"),
        )

        cr.execute(query)

    _logger.info("Migration completed successfully.")
