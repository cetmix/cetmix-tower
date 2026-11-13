# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    def _prepare_backup_values(self, *args, **kwargs):
        """Capture source grouping, remotes and aggregator settings.

        Args:
            *args (tuple): Backup Template passed to the parent hook.
            **kwargs (dict): Name, custom values and triggering command.

        Returns:
            dict: Backup values with a portable Git Project snapshot.
        """
        vals = super()._prepare_backup_values(*args, **kwargs)
        project = self.git_project_id
        if project:
            vals["git_project_data"] = {
                "sources": [
                    {
                        "name": source.name,
                        "sequence": source.sequence,
                        "enabled": source.enabled,
                        "remotes": [
                            {
                                "repo_url": remote.repo_id.url,
                                "is_private": remote.repo_id.is_private,
                                "head_type": remote.head_type,
                                "head": remote.head,
                                "url_protocol": remote.url_protocol,
                                "enabled": remote.enabled,
                                "sequence": remote.sequence,
                            }
                            for remote in source.remote_ids
                        ],
                    }
                    for source in project.source_ids.sorted(
                        lambda source: (source.sequence, source.name or "")
                    )
                ],
                "git_aggregator_root_dir": project.git_aggregator_root_dir,
                "note": project.note,
            }
        return vals
