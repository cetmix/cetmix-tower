import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Move SSH credentials, host keys, SSH keys, and secret values
    to the vault-backed storage.

    """

    # 1. SSH password and host key are now stored in secrets
    _logger.info("Moving SSH password and host key to vault.")
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Read SSH password and host key from servers using SQL query
    cr.execute(
        """
        SELECT id, ssh_password, host_key
        FROM cx_tower_server
        WHERE ssh_password IS NOT NULL OR host_key IS NOT NULL
    """
    )
    server_records = cr.fetchall()
    server_model = env["cx.tower.server"]
    success = False
    try:
        for record in server_records:
            _logger.info(
                f"Moving SSH password and host key to vault for server {record[0]}"
            )
            server_model.browse(record[0]).write(
                {"ssh_password": record[1], "host_key": record[2]}
            )
        _logger.info("Moving SSH password and host key to vault completed.")
        success = True
    # Clear SSH password and host key from servers
    except Exception as e:
        _logger.error(f"Error moving SSH password and host key to vault: {e}")
        raise e
    finally:
        if success:
            cr.execute(
                """
                UPDATE cx_tower_server
                SET ssh_password = NULL, host_key = NULL
                WHERE ssh_password IS NOT NULL OR host_key IS NOT NULL
            """
            )
            _logger.info("Cleared SSH password and host key from servers.")

    # 2. SSH keys are now stored in secrets
    _logger.info("Moving SSH keys to vault.")
    success = False
    # Read SSH keys from keys using SQL query
    cr.execute(
        """
        SELECT id, secret_value
        FROM cx_tower_key
        WHERE key_type = 'k'
    """
    )
    ssh_key_records = cr.fetchall()
    ssh_key_model = env["cx.tower.key"]
    try:
        for record in ssh_key_records:
            _logger.info(f"Moving SSH key to vault record {record[0]}")
            ssh_key_model.browse(record[0]).write({"secret_value": record[1]})
        _logger.info("Moving SSH keys to vault completed.")
        success = True
    except Exception as e:
        _logger.error(f"Error moving SSH keys to vault: {e}")
        raise e
    finally:
        if success:
            # Clear SSH key from keys
            cr.execute(
                """
                UPDATE cx_tower_key
                SET secret_value = NULL
                WHERE secret_value IS NOT NULL
            """
            )
            _logger.info("Cleared SSH key from keys.")

    # 3. Secret values are now stored in secrets
    _logger.info("Moving secret values to vault.")
    success = False
    # Read secret values from key values using SQL query
    cr.execute(
        """
        SELECT id, secret_value
        FROM cx_tower_key_value
    """
    )
    secret_value_records = cr.fetchall()
    secret_value_model = env["cx.tower.key.value"]
    try:
        for record in secret_value_records:
            _logger.info(f"Moving secret value to vault record {record[0]}")
            secret_value_model.browse(record[0]).write({"secret_value": record[1]})
        _logger.info("Moving secret values to vault completed.")
        success = True
    except Exception as e:
        _logger.error(f"Error moving secret values to vault: {e}")
        raise e
    finally:
        if success:
            # Clear secret value from key values
            cr.execute(
                """
                UPDATE cx_tower_key_value
                SET secret_value = NULL
                WHERE secret_value IS NOT NULL
            """
            )
            _logger.info("Cleared secret value from key values.")
