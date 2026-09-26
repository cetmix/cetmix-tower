import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Link git remotes to repositories and clean URL-shaped heads.

    A database upgraded through 16.0.2.0.0 already created repositories
    from ``cx_tower_git_remote.url``. Odoo then dropped that column, so
    selecting it fails on the way to 17.0. An earlier 17.0 database still
    has the column and must be converted here. Head cleanup runs either way.

    Args:
        cr (odoo.sql_db.Cursor): Database cursor of the upgrade transaction.
        version (str): Module version installed before this script runs.

    Returns:
        None

    Raises:
        ValidationError: If a legacy remote URL cannot be parsed into a
            repository.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    remote_obj = env["cx.tower.git.remote"]
    repo_obj = env["cx.tower.git.repo"]
    url_count = 0

    # 16.0.2.0.0 already removed this column. Earlier 17.0 still has it.
    if column_exists(cr, "cx_tower_git_remote", "url"):
        _logger.info(
            "Converting URLs in remotes to repositories and adding"
            " repo_id to remotes."
        )
        # Group remotes that still store a URL on the remote itself.
        cr.execute(
            """
            SELECT url, array_agg(id) as remote_ids
            FROM cx_tower_git_remote
            GROUP BY url
        """
        )
        remote_urls = cr.fetchall()
        remote_urls_dict = {url: remote_ids for url, remote_ids in remote_urls}

        for url, remote_ids in remote_urls_dict.items():
            repo_id = repo_obj.name_create(url)[0]
            # Check if any of the remotes is private
            remotes = remote_obj.browse(remote_ids)
            is_private = bool(remotes.filtered(lambda r: r.is_private))

            # Add repo to remotes
            # We are using SQL to avoid post-write triggers
            cr.execute(
                """
                UPDATE cx_tower_git_remote
                SET repo_id = %s
                WHERE id = ANY(%s)
            """,
                (repo_id, remote_ids),
            )

            # Update repo.is_private
            # We are using SQL to avoid post-write triggers
            if is_private:
                cr.execute(
                    """
                    UPDATE cx_tower_git_repo
                    SET is_private = true
                    WHERE id = %s
                """,
                    (repo_id,),
                )

            url_count += 1
    else:
        _logger.info(
            "Skipping remote URL conversion while upgrading from %s:"
            " cx_tower_git_remote.url was already removed.",
            version,
        )

    # Compute project_ids for repositories
    _logger.info("Computing project_ids for repositories.")
    remote_obj.invalidate_model()
    repo_obj.invalidate_model()
    repo_obj.search([])._compute_git_project_ids()

    # Sanitize remote heads that contain URLs (but preserve legitimate branch names)
    # Use the SQL query to avoid post-write triggers
    # Only sanitize if head looks like a URL
    # (starts with http://, https://, git://, or contains domain patterns)
    _logger.info("Sanitizing remote heads that contain URLs.")
    cr.execute(
        """
        UPDATE cx_tower_git_remote
        SET head = (regexp_match(head, '[^/]+$'))[1]
        WHERE head LIKE '%/%'
        AND (
            head ~* '^https?://'
            OR head ~* '^git://'
            OR head ~* '@[a-zA-Z0-9.-]+:'
            OR head ~* '[a-zA-Z0-9.-]+[.][a-zA-Z]{2,}/'
        )
    """
    )

    _logger.info("Migration completed. %s unique urls processed", url_count)
