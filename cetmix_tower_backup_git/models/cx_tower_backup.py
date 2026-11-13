# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerBackup(models.Model):
    _inherit = "cx.tower.backup"

    git_project_data = fields.Json(readonly=True)

    def _prepare_restored_jet(self, jet):
        """Build a fresh project before the Restore plan's first line.

        Args:
            jet (cx.tower.jet): Destination Jet.

        Returns:
            None: Saved Git settings have been restored when applicable.

        Raises:
            ValidationError: A saved repository URL is invalid.
        """
        super()._prepare_restored_jet(jet)
        data = self.git_project_data or {}
        sources = [
            source for source in data.get("sources", []) if source.get("remotes")
        ]
        if not jet.jet_template_id.use_git_projects or not sources:
            return
        project = self.env["cx.tower.git.project"]._create_named_git_project(jet.name)
        project.write(
            {
                key: data[key]
                for key in ("git_aggregator_root_dir", "note")
                if data.get(key)
            }
        )
        source_model = self.env["cx.tower.git.source"]
        remote_model = self.env["cx.tower.git.remote"]
        repo_model = self.env["cx.tower.git.repo"]
        for source_data in sources:
            source = source_model.create(
                {
                    "git_project_id": project.id,
                    **{
                        key: source_data[key] for key in ("name", "sequence", "enabled")
                    },
                }
            )
            remote_values = []
            for remote in source_data["remotes"]:
                repo_id = repo_model._get_repo_id_by_url(
                    remote["repo_url"], raise_if_invalid=True
                )
                if not repo_id:
                    repo_id = repo_model._get_repo_id_by_url(
                        remote["repo_url"], create=True, raise_if_invalid=True
                    )
                    if "is_private" in remote:
                        repo_model.browse(repo_id).is_private = remote["is_private"]
                remote_values.append(
                    {
                        "source_id": source.id,
                        "repo_id": repo_id,
                        **{
                            key: remote[key]
                            for key in (
                                "head_type",
                                "head",
                                "url_protocol",
                                "enabled",
                                "sequence",
                            )
                        },
                    }
                )
            remote_model.create(remote_values)
        jet.git_project_id = project
