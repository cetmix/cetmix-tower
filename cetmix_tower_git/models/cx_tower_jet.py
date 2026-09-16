# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJet(models.Model):
    """Extend Jets with a Git Project."""

    _inherit = "cx.tower.jet"

    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        ondelete="set null",
        index=True,
        copy=False,
        help="Git Project of this Jet. Several Jets may share a project.",
    )
    git_remote_ids = fields.One2many(
        comodel_name="cx.tower.git.remote",
        compute="_compute_git_remote_ids",
        string="Repositories",
        readonly=False,
        copy=False,
    )
    git_project_readonly = fields.Boolean(
        compute="_compute_git_project_readonly",
    )
    git_project_readonly_reason = fields.Char(
        compute="_compute_git_project_readonly",
    )

    @api.depends(
        "git_project_id",
        "git_project_id.source_ids",
        "git_project_id.source_ids.remote_ids",
        "git_project_id.source_ids.remote_ids.sequence",
        "git_project_id.source_ids.sequence",
    )
    def _compute_git_remote_ids(self):
        """Fill the Git Project tab from the project's flat remote list."""
        for jet in self:
            if not jet.git_project_id:
                jet.git_remote_ids = False
                continue
            jet.git_remote_ids = jet.git_project_id._get_flat_remotes()

    @api.depends(
        "git_project_id",
        "git_project_id.jet_ids.manager_ids",
        "git_project_id.jet_ids.user_ids",
        "git_project_id.jet_ids.server_id.user_ids",
        "git_project_id.jet_ids.server_id.manager_ids",
        "manager_ids",
        "user_ids",
        "server_id.user_ids",
        "server_id.manager_ids",
    )
    @api.depends_context("uid")
    def _compute_git_project_readonly(self):
        """Set the tab notice when the user cannot edit the Git Project."""
        for jet in self:
            readonly = False
            reason = ""
            if jet.has_access("write") is False:
                readonly = True
                reason = _("You cannot modify this Jet.")
            elif jet.git_project_id and not jet.git_project_id.has_access("write"):
                readonly = True
                reason = _(
                    "This Git Project is shared with Jets you cannot modify."
                    " You can view the repositories but cannot edit them."
                )
            jet.git_project_readonly = readonly
            jet.git_project_readonly_reason = reason

    @api.model_create_multi
    def create(self, vals_list):
        """Create Jets after checking write access on linked Git Projects.

        Args:
            vals_list (list): Values for the new Jets.

        Returns:
            recordset: Created ``cx.tower.jet`` records.
        """
        commands_list = [vals.pop("git_remote_ids", None) for vals in vals_list]
        has_project = [bool(vals.get("git_project_id")) for vals in vals_list]
        for vals in vals_list:
            self._check_git_project_link_access(vals.get("git_project_id"))
        jets = super().create(vals_list)
        for jet, commands, linked in zip(
            jets, commands_list, has_project, strict=False
        ):
            to_apply = commands
            if linked:
                to_apply = self._without_git_remote_replace_commands(commands)
            if to_apply:
                jet._apply_git_remote_commands(to_apply)
        return jets

    def write(self, vals):
        """Write Jet values, renaming or relinking the Git Project.

        Args:
            vals (dict): Values to write.

        Returns:
            bool: Always ``True``.
        """
        commands = vals.pop("git_remote_ids", None)
        project_in_vals = "git_project_id" in vals
        if project_in_vals:
            self._check_git_project_link_access(vals.get("git_project_id"))
            old_projects = {jet.id: jet.git_project_id for jet in self}
        else:
            old_projects = {}
        res = super().write(vals)
        if vals.get("name"):
            for jet in self:
                project = jet.git_project_id
                if project and project.jet_ids == jet:
                    project.write({"name": jet.name})
        if project_in_vals:
            new_project = self._git_project_from_val(vals.get("git_project_id"))
            for jet in self:
                old_project = old_projects.get(jet.id)
                if not new_project:
                    continue
                if old_project == new_project:
                    continue
                jet._relink_git_files(new_project)
        if commands is not None:
            for jet in self:
                to_apply = commands
                if project_in_vals and old_projects.get(jet.id) != jet.git_project_id:
                    to_apply = self._without_git_remote_replace_commands(commands)
                if to_apply:
                    jet._apply_git_remote_commands(to_apply)
        return res

    def unlink(self):
        """Delete Jets and orphan Git Projects that no record uses.

        Returns:
            bool: Result of ``super().unlink()``.
        """
        projects = self.git_project_id
        res = super().unlink()
        for project in projects.exists():
            project_sudo = project.sudo()
            if project_sudo._is_orphan_git_project():
                project_sudo.unlink()
        return res

    def _git_project_from_val(self, value):
        """Return a Git Project recordset from a write/create value.

        Args:
            value (int | cx.tower.git.project | bool): Project id,
                recordset, or falsy.

        Returns:
            recordset: ``cx.tower.git.project``, possibly empty.
        """
        if not value:
            return self.env["cx.tower.git.project"]
        if isinstance(value, models.BaseModel):
            return value
        return self.env["cx.tower.git.project"].browse(value)

    def _check_git_project_link_access(self, value):
        """Ensure the caller can write a Git Project being linked to a Jet.

        Many2one assignment does not check access on the comodel, and
        ``exists()`` ignores record rules. Without this check a manager
        could attach any project id and inherit Jet-based access.

        Args:
            value (int | cx.tower.git.project | bool): Project id,
                recordset, or falsy.

        Raises:
            AccessError: If the user cannot write the project.
        """
        project = self._git_project_from_val(value)
        if project:
            project.check_access("write")

    def _without_git_remote_replace_commands(self, commands):
        """Drop CLEAR/SET commands from a Git Project tab write.

        Changing ``git_project_id`` makes the computed remotes list
        dirty. The web client then sends Command.SET of the tab's
        current ids. An empty tab becomes SET ``[]``, which would
        replace the selected project's remotes.

        Args:
            commands (list | None): One2many commands for
                ``git_remote_ids``.

        Returns:
            list: Commands excluding CLEAR (5) and SET (6).
        """
        return [
            command
            for command in (commands or [])
            if command and command[0] not in (fields.Command.CLEAR, fields.Command.SET)
        ]

    def _apply_git_remote_commands(self, commands):
        """Apply Git Project tab x2many commands through repo lines.

        The handle widget writes unique ``sequence`` values in visual
        order. When those values are unique they are the flat-list order
        (§5.3). CREATE lines are appended so a line added at the bottom
        stays last.

        Args:
            commands (list): One2many commands for ``git_remote_ids``.

        Returns:
            bool: Always ``True``.
        """
        self.ensure_one()
        lines = []
        if self.git_project_id:
            lines = [
                self._git_remote_to_line(remote)
                for remote in self.git_project_id._get_flat_remotes()
            ]
        by_id = {line["remote_id"]: line for line in lines}
        created = []
        remote_model = self.env["cx.tower.git.remote"]
        for command in commands or []:
            if command:
                self._apply_git_remote_command(
                    command, lines, by_id, created, remote_model
                )
        remaining = [line for line in lines if line.get("remote_id") in by_id]
        sequences = [line["_sequence"] for line in remaining]
        if remaining and len(sequences) == len(set(sequences)):
            remaining = sorted(remaining, key=lambda line: line["_sequence"])
        result = []
        for line in remaining + created:
            line.pop("_sequence", None)
            if not line.get("repo_id"):
                continue
            result.append(line)
        if not self.git_project_id and not result:
            return True
        return self.set_git_repo_lines(result)

    def _apply_git_remote_command(self, command, lines, by_id, created, remote_model):
        """Apply one Git Project tab x2many command.

        Args:
            command (tuple): One2many command.
            lines (list): Current repo line dicts. Mutated in place.
            by_id (dict): Lines keyed by remote id. Mutated in place.
            created (list): CREATE line dicts. Mutated in place.
            remote_model (cx.tower.git.remote): Remote model.
        """
        code = command[0]
        if code == 0:
            created.append(self._git_remote_vals_to_line(command[2] or {}))
            return
        if code == 1:
            line = by_id.get(command[1])
            if line:
                line.update(
                    self._git_remote_vals_to_line(command[2] or {}, partial=True)
                )
            return
        if code in (2, 3):
            by_id.pop(command[1], None)
            lines[:] = [line for line in lines if line.get("remote_id") != command[1]]
            return
        if code == 4:
            # Web client keeps DELETE after switching project, then
            # LINK when the same remotes are shown again. Restore
            # only remotes that still belong to this Jet's project.
            remote_id = command[1]
            if not remote_id or remote_id in by_id:
                return
            remote = remote_model.browse(remote_id)
            if (
                not remote.exists()
                or not self.git_project_id
                or remote.git_project_id != self.git_project_id
            ):
                return
            line = self._git_remote_to_line(remote)
            lines.append(line)
            by_id[remote.id] = line
            return
        if code == 5:
            lines.clear()
            by_id.clear()
            return
        if code == 6:
            ids = command[2] or []
            lines[:] = [by_id[rid] for rid in ids if rid in by_id]
            by_id.clear()
            by_id.update({line["remote_id"]: line for line in lines})

    def _git_remote_to_line(self, remote):
        """Return a repo line dict for an existing remote.

        Args:
            remote (cx.tower.git.remote): Remote to convert.

        Returns:
            dict: Repo line keys plus ``_sequence``.
        """
        return {
            "remote_id": remote.id,
            "repo_id": remote.repo_id.id,
            "url_protocol": remote.url_protocol or "https",
            "head_type": remote.head_type,
            "head": remote.head,
            "enabled": bool(remote.enabled),
            "_sequence": remote.sequence,
        }

    def _git_remote_vals_to_line(self, vals, partial=False):
        """Convert a remote command payload to a repo line dict.

        Args:
            vals (dict): Values from a CREATE or UPDATE command.
            partial (bool): If ``True``, only include keys present in
                ``vals``. Defaults to ``False``.

        Returns:
            dict: Repo line keys, plus ``_sequence`` when known.
        """
        line = {}
        if not partial:
            line["url_protocol"] = "https"
            line["enabled"] = True
            line["_sequence"] = vals.get("sequence", 10)
        repo = vals.get("repo_id")
        if repo:
            line["repo_id"] = repo.id if isinstance(repo, models.BaseModel) else repo
        for key in ("url_protocol", "head_type", "head", "enabled"):
            if key in vals:
                line[key] = vals[key]
        if "sequence" in vals:
            line["_sequence"] = vals["sequence"]
        return line

    def get_git_repo_lines(self):
        """Return this Jet's Git Project remotes as repo line dicts.

        Returns:
            list: Repo line dicts, or ``[]`` when the Jet has no project.
        """
        self.ensure_one()
        if not self.git_project_id:
            return []
        return self.git_project_id.get_repo_lines()

    def add_git_repo_lines(self, lines):
        """Append repo lines to this Jet's Git Project.

        Creates a project named after the Jet when it has none.

        Args:
            lines (list): List of repo line dicts.

        Returns:
            bool: Always ``True``.
        """
        return self._ensure_git_project().add_repo_lines(lines)

    def set_git_repo_lines(self, lines):
        """Replace this Jet's Git Project remotes with ``lines``.

        Creates a project named after the Jet when it has none.

        Args:
            lines (list): List of repo line dicts.

        Returns:
            bool: Always ``True``.
        """
        return self._ensure_git_project().set_repo_lines(lines)

    def _ensure_git_project(self):
        """Return this Jet's Git Project, creating one if needed.

        Returns:
            recordset: ``cx.tower.git.project``.
        """
        self.ensure_one()
        if not self.git_project_id:
            self.git_project_id = self.env[
                "cx.tower.git.project"
            ]._create_named_git_project(self.name)
        return self.git_project_id

    def action_open_git_project(self):
        """Open the Git Project form.

        Returns:
            dict: Window action.
        """
        self.ensure_one()
        if not self.git_project_id:
            raise ValidationError(_("This Jet has no Git Project."))
        return {
            "type": "ir.actions.act_window",
            "name": self.git_project_id.name,
            "res_model": "cx.tower.git.project",
            "res_id": self.git_project_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _relink_git_files(self, new_project):
        """Move this Jet's git file links to ``new_project``.

        Args:
            new_project (cx.tower.git.project): Project to link to.
        """
        self.ensure_one()
        rel_model = self.env["cx.tower.git.project.rel"]
        links = rel_model.search([("file_id", "in", self.file_ids.ids)])
        for link in links:
            existing = rel_model.search(
                [
                    ("git_project_id", "=", new_project.id),
                    ("file_id", "=", link.file_id.id),
                    ("project_format", "=", link.project_format),
                    ("id", "!=", link.id),
                ],
                limit=1,
            )
            if existing:
                link.unlink()
            else:
                link.write({"git_project_id": new_project.id})
