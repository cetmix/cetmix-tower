# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CxTowerGitRepoLineWizard(models.TransientModel):
    """Transient repo line used by the Jet launch and clone wizards."""

    _name = "cx.tower.git.repo.line.wizard"
    _description = "Git Repository Line"
    _order = "sequence, id"

    create_wizard_id = fields.Many2one(
        comodel_name="cx.tower.jet.create.wizard",
        ondelete="cascade",
    )
    clone_wizard_id = fields.Many2one(
        comodel_name="cx.tower.jet.clone.wizard",
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    repo_id = fields.Many2one(
        comodel_name="cx.tower.git.repo",
        string="Repository",
        required=True,
        ondelete="cascade",
    )
    url_protocol = fields.Selection(
        selection=[
            ("ssh", "SSH"),
            ("https", "HTTPS"),
            ("git", "GIT"),
        ],
        string="Protocol",
        required=True,
        default="https",
    )
    head_type = fields.Selection(
        selection=[
            ("branch", "Branch"),
            ("pr", "Pull/Merge Request"),
            ("commit", "Commit"),
        ],
        required=True,
    )
    head = fields.Char(required=True)
    enabled = fields.Boolean(default=True)

    def _to_repo_line_dict(self):
        """Serialize this line to the public repo line format.

        Returns:
            dict: Repo line dict using ``repo_id``.
        """
        self.ensure_one()
        return {
            "repo_id": self.repo_id.id,
            "url_protocol": self.url_protocol,
            "head_type": self.head_type,
            "head": self.head,
            "enabled": bool(self.enabled),
        }


class CxTowerJetCreateWizard(models.TransientModel):
    """Launch wizard: add repositories to the new Jet."""

    _inherit = "cx.tower.jet.create.wizard"

    add_repositories = fields.Selection(
        selection=[
            ("no", "No"),
            ("existing", "Existing Project"),
            ("repos", "Select repos"),
        ],
        string="Add repositories",
        required=True,
        default="no",
    )
    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        string="Git Project",
    )
    git_repo_line_ids = fields.One2many(
        comodel_name="cx.tower.git.repo.line.wizard",
        inverse_name="create_wizard_id",
        string="Repositories",
    )

    def action_confirm(self):
        """Create a new jet, passing Git Project keyword arguments.

        Returns:
            dict: Window action opening the created Jet.
        """
        self.ensure_one()

        if not self.server_id:
            raise ValidationError(_("Please select a server to create a jet."))

        kwargs = {}

        variable_values = {}
        if self.use_custom_variables == "y" and self.line_ids:
            variable_values = {
                line.variable_id.reference: line.value_char for line in self.line_ids
            }
            kwargs["variable_values"] = variable_values

        if self.partner_id:
            kwargs["partner_id"] = self.partner_id.id

        if self.url_type == "m" and self.url:
            kwargs["url"] = self.url

        kwargs.update(self._get_git_jet_kwargs())

        jet = self.jet_template_id.create_jet(
            self.server_id,
            name=self.name,
            state=self.state_id,
            **kwargs,
        )
        if not jet:
            raise ValidationError(
                _(
                    "Failed to create jet. "
                    "Please check the server and template settings."
                )
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet",
            "res_id": jet.id,
            "view_mode": "form",
            "target": "current",
        }

    def _get_git_jet_kwargs(self):
        """Return Git keyword arguments for ``create_jet``.

        Returns:
            dict: Keyword arguments, possibly empty.
        """
        self.ensure_one()
        if self.add_repositories == "existing":
            if not self.git_project_id:
                raise ValidationError(_("Please select a Git Project."))
            return {"git_project": self.git_project_id.id}
        if self.add_repositories == "repos":
            if not self.git_repo_line_ids:
                raise ValidationError(
                    _("Please add at least one repository to create a Git Project.")
                )
            return {
                "git_repo_lines": [
                    line._to_repo_line_dict() for line in self.git_repo_line_ids
                ]
            }
        return {}


class CxTowerJetCloneWizard(models.TransientModel):
    """Clone wizard: choose how the clone gets its Git Project."""

    _inherit = "cx.tower.jet.clone.wizard"

    git_project_mode = fields.Selection(
        selection=[
            ("copy", "Copy parent"),
            ("keep", "Keep parent"),
            ("select", "Select"),
            ("repos", "Add repos"),
        ],
        string="Git Project",
        required=True,
        default="copy",
    )
    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        string="Existing Project",
    )
    git_repo_line_ids = fields.One2many(
        comodel_name="cx.tower.git.repo.line.wizard",
        inverse_name="clone_wizard_id",
        string="Repositories",
    )
    parent_git_project_id = fields.Many2one(
        related="jet_id.git_project_id",
        string="Parent Git Project",
    )

    def action_confirm(self):
        """Clone the jet, passing Git Project keyword arguments.

        Returns:
            dict: Window action opening the cloned Jet.
        """
        self.ensure_one()
        kwargs = {}

        custom_variables = {}
        if self.line_ids:
            custom_variables = {
                line.variable_id.reference: line.value_char for line in self.line_ids
            }
        if custom_variables:
            kwargs["variable_values"] = custom_variables

        if self.partner_id:
            kwargs["partner_id"] = self.partner_id.id

        if self.url_type == "m" and self.url:
            kwargs["url"] = self.url

        kwargs.update(self._get_git_jet_kwargs())

        jet = self.jet_id.clone(
            server=self.server_id,
            name=self.name,
            state=self.state_id,
            **kwargs,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet",
            "res_id": jet.id,
            "view_mode": "form",
            "target": "current",
        }

    def _get_git_jet_kwargs(self):
        """Return Git keyword arguments for ``clone``.

        Returns:
            dict: Keyword arguments, possibly empty.
        """
        self.ensure_one()
        parent_project = self.jet_id.git_project_id
        if not parent_project:
            return {}
        if self.git_project_mode == "copy":
            return {"git_project_copy_from": parent_project.id}
        if self.git_project_mode == "keep":
            return {"git_project": parent_project.id}
        if self.git_project_mode == "select":
            if not self.git_project_id:
                raise ValidationError(_("Please select a Git Project."))
            return {"git_project": self.git_project_id.id}
        if self.git_project_mode == "repos":
            if not self.git_repo_line_ids:
                raise ValidationError(
                    _("Please add at least one repository to create a Git Project.")
                )
            return {
                "git_repo_lines": [
                    line._to_repo_line_dict() for line in self.git_repo_line_ids
                ]
            }
        return {}
