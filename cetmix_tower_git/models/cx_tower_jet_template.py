# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import ValidationError


class CxTowerJetTemplate(models.Model):
    """Create or copy a Git Project when a Jet is launched or cloned."""

    _inherit = "cx.tower.jet.template"

    def _prepare_jet_values(self, server, name=None, **kwargs):
        """Prepare Jet values, attaching a Git Project when requested.

        Git keyword arguments (at most one of the three):

        * ``git_project``: project id or reference to link (not copied).
        * ``git_project_copy_from``: project id or reference to copy,
          named after the new Jet.
        * ``git_repo_lines``: list of repo line dicts used to create a
          new project named after the new Jet.

        If none is given and ``kwargs`` contains ``jet_cloned_from_id``,
        the parent Jet's project is copied (clone default).
        ``jet_cloned_from_id`` is read and left in ``kwargs`` for
        ``super()``.

        Args:
            server (cx.tower.server): Server to create the Jet on.
            name (str, optional): Requested Jet name.
            **kwargs: Additional values. Git keys are popped before
                ``super()``.

        Returns:
            dict: Values for ``cx.tower.jet.create``.
        """
        git_project = kwargs.pop("git_project", None)
        git_project_copy_from = kwargs.pop("git_project_copy_from", None)
        git_repo_lines = kwargs.pop("git_repo_lines", None)

        provided = [
            key
            for key, value in (
                ("git_project", git_project),
                ("git_project_copy_from", git_project_copy_from),
                ("git_repo_lines", git_repo_lines),
            )
            if (value is not None if key == "git_repo_lines" else value)
        ]
        if len(provided) > 1:
            raise ValidationError(
                _(
                    "Only one of git_project, git_project_copy_from"
                    " or git_repo_lines may be given."
                )
            )

        if not provided:
            cloned_from_id = kwargs.get("jet_cloned_from_id")
            if cloned_from_id:
                parent = self.env["cx.tower.jet"].browse(cloned_from_id)
                if parent.git_project_id:
                    git_project_copy_from = parent.git_project_id.id

        vals = super()._prepare_jet_values(server, name=name, **kwargs)

        project = self._prepare_jet_git_project(
            vals["name"],
            git_project=git_project,
            git_project_copy_from=git_project_copy_from,
            git_repo_lines=git_repo_lines,
        )
        if project:
            vals["git_project_id"] = project.id
        return vals

    def _prepare_jet_git_project(
        self,
        jet_name,
        git_project=None,
        git_project_copy_from=None,
        git_repo_lines=None,
    ):
        """Create, copy or resolve the Git Project for a new Jet.

        Args:
            jet_name (str): Final Jet name, used as the project name.
            git_project (int | str, optional): Project id or reference
                to link.
            git_project_copy_from (int | str, optional): Project id or
                reference to copy.
            git_repo_lines (list, optional): Repo line dicts.

        Returns:
            recordset: ``cx.tower.git.project`` or empty.
        """
        project_model = self.env["cx.tower.git.project"]
        if git_project:
            return self._resolve_git_project_arg(git_project, operation="write")
        if git_project_copy_from:
            source = self._resolve_git_project_arg(
                git_project_copy_from, operation="read"
            )
            return source._copy_named(jet_name)
        if git_repo_lines is not None:
            if not git_repo_lines:
                raise ValidationError(
                    _("Please add at least one repository to create a Git Project.")
                )
            project = project_model._create_named_git_project(jet_name)
            project.add_repo_lines(git_repo_lines)
            return project
        return project_model

    def _resolve_git_project_arg(self, value, operation="read"):
        """Resolve a Git Project from an id or a reference string.

        Args:
            value (int | str): Project id or reference.
            operation (str): Access operation to check after resolving.
                Defaults to ``read``. Use ``write`` when linking the
                project to a Jet.

        Returns:
            recordset: Single ``cx.tower.git.project``.

        Raises:
            ValidationError: If the project cannot be resolved.
            AccessError: If the user cannot perform ``operation``.
        """
        project_model = self.env["cx.tower.git.project"]
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            project = project_model.browse(int(value))
            if not project.exists():
                raise ValidationError(
                    _("Git Project id %(project_id)s was not found.", project_id=value)
                )
        else:
            project = project_model.get_by_reference(value)
            if not project:
                raise ValidationError(
                    _(
                        "Git Project reference '%(reference)s' was not found.",
                        reference=value,
                    )
                )
        project.check_access(operation)
        return project
