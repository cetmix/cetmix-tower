import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Convert URLs in remotes to repositories.
    Add repo_id to remotes.
    """

    _logger.info(
        "Converting URLs in remotes to repositories and adding repo_id to remotes."
    )
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Fetch all remotes using SQL query Group them {"url": [remote_id, remote_id, ...]}
    cr.execute(
        """
        SELECT url, array_agg(id) as remote_ids
        FROM cx_tower_git_remote
        GROUP BY url
    """
    )
    remote_urls = cr.fetchall()
    remote_urls_dict = {url: remote_ids for url, remote_ids in remote_urls}

    # Create repo for each url and add this repo to all remotes
    url_count = 0
    remote_obj = env["cx.tower.git.remote"]
    repo_obj = env["cx.tower.git.repo"]
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

    # Compute project_ids for repositories
    _logger.info("Computing project_ids for repositories.")
    remote_obj.invalidate_model()
    repo_obj.invalidate_model()
    repo_obj.search([])._compute_git_project_ids()

    # Sanitize all remote heads that contain a slash
    # Use the SQL query to avoid post-write triggers
    _logger.info("Sanitizing remote heads that contain a slash.")
    cr.execute(
        """
        UPDATE cx_tower_git_remote
        SET head = (regexp_match(head, '[^/]+$'))[1]
        WHERE head LIKE '%/%'
    """
    )

    _logger.info("Migration completed. %s unique urls processed", url_count)
