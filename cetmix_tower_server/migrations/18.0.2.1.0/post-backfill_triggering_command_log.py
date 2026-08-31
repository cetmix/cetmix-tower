# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill triggering_command_log_id from triggered_plan_log_id.

    Records created before triggering_command_log_id existed only stored the
    reverse Many2one on the command log. After this backfill, plan_log.finish()
    can close the parent command without searching cx_tower_command_log.
    """
    cr.execute(
        """
        UPDATE cx_tower_plan_log AS plan_log
           SET triggering_command_log_id = command_log.id
          FROM (
            SELECT DISTINCT ON (triggered_plan_log_id)
                   id,
                   triggered_plan_log_id
              FROM cx_tower_command_log
             WHERE triggered_plan_log_id IS NOT NULL
             ORDER BY triggered_plan_log_id, id DESC
          ) AS command_log
         WHERE command_log.triggered_plan_log_id = plan_log.id
           AND plan_log.triggering_command_log_id IS NULL
        """
    )
    _logger.info(
        "Backfilled triggering_command_log_id on %s flight plan logs",
        cr.rowcount,
    )
