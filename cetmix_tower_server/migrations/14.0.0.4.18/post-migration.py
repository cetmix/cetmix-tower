import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Fix migration in 14.0.0.4.17
    Create secret values.
    """
    _logger.info("Starting SQL migration for global secret values.")

    # Get all keys that are related to a server or a partner
    cr.execute(
        """
        SELECT k.id, k.reference, k.secret_value, k.server_id, k.partner_id
        FROM cx_tower_key k
        WHERE k.key_type = 's'
        AND (k.server_id IS NOT NULL OR k.partner_id IS NOT NULL)
    """
    )
    keys_to_merge = cr.fetchall()

    for key_id, reference, secret_value, server_id, partner_id in keys_to_merge:
        # Find or use current key as main key
        cr.execute(
            """
            SELECT id FROM cx_tower_key
            WHERE reference = %s AND server_id IS NULL AND partner_id IS NULL
            LIMIT 1
        """,
            (reference,),
        )
        main_key = cr.fetchone()
        main_key_id = main_key[0] if main_key else key_id

        # Create key value
        cr.execute(
            """
            INSERT INTO cx_tower_key_value
            (key_id, server_id, partner_id, secret_value,
            create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, %s, 1, now(), 1, now())
        """,
            (main_key_id, server_id, partner_id, secret_value),
        )

    # Remove migrated keys that don't have values
    cr.execute(
        """
        DELETE FROM cx_tower_key k
        WHERE k.key_type = 's'
        AND (k.server_id IS NOT NULL OR k.partner_id IS NOT NULL)
        AND NOT EXISTS (
            SELECT 1 FROM cx_tower_key_value v WHERE v.key_id = k.id
        )
    """
    )

    # Create global secret values
    # Get all keys that are related to a server or a partner
    cr.execute(
        """
        SELECT k.id, k.secret_value
        FROM cx_tower_key k
        WHERE k.key_type = 's'
    """
    )
    keys = cr.fetchall()

    for key_id, secret_value in keys:
        # Create global value
        cr.execute(
            """
            INSERT INTO cx_tower_key_value
            (key_id, secret_value,
            create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, 1, now(), 1, now())
            AND NOT EXISTS (
                SELECT 1 FROM cx_tower_key_value v
                WHERE v.key_id = %s AND v.server_id IS NULL AND v.partner_id IS NULL
            )
        """,
            (key_id, secret_value, key_id),
        )

    _logger.info("SQL migration completed successfully.")
