# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJetCreateWizard(models.TransientModel):
    """Create new jet from template"""

    _name = "cx.tower.jet.create.wizard"
    _description = "Create new jet"

    name = fields.Char(help="The name of the jet")
    name_type = fields.Selection(
        selection=[("a", "will be auto-generated"), ("m", "I will put myself")],
        default="a",
        required=True,
    )
    note = fields.Text(related="jet_template_id.note", readonly=True)
    url = fields.Char(help="The URL of the jet")
    url_type = fields.Selection(
        selection=[("a", "will be auto-generated"), ("m", "I will put myself")],
        default="a",
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        compute="_compute_partner_id",
        store=True,
        readonly=False,
        help="Partner associated with the jet",
    )
    jet_template_id = fields.Many2one(
        "cx.tower.jet.template",
        required=True,
    )
    jet_template_domain = fields.Binary(
        compute="_compute_jet_template_domain",
        help="Domain for jet template",
    )
    jet_template_message = fields.Text(
        compute="_compute_jet_template_domain",
        help="Message for the user",
    )
    server_domain = fields.Binary(
        compute="_compute_server_domain",
        help="Domain for server",
    )
    server_id = fields.Many2one(
        "cx.tower.server",
    )
    state_id = fields.Many2one("cx.tower.jet.state", help="Requested state of the jet")
    state_domain = fields.Binary(compute="_compute_state_domain")
    use_custom_variables = fields.Selection(
        selection=[("n", "default settings"), ("y", "custom settings")],
        default="n",
        required=True,
    )
    line_ids = fields.One2many(
        "cx.tower.jet.create.wizard.variable.line",
        "wizard_id",
        string="Variable Lines",
    )

    @api.depends("server_id")
    def _compute_partner_id(self):
        """
        Compute the partner associated with the jet
        """
        for wizard in self:
            # Do not modify partner if it is already set
            if wizard.partner_id:
                continue
            # Set partner from server
            if wizard.server_id and wizard.server_id.partner_id:
                wizard.partner_id = wizard.server_id.partner_id.id

    @api.depends("server_id")
    def _compute_jet_template_domain(self):
        """
        Compute the domain and message for the jet templates
        """
        template_obj = self.env["cx.tower.jet.template"]
        all_templates_domain = [("show_in_create_wizard", "=", True)]
        all_templates = template_obj.search(all_templates_domain)
        for wizard in self:
            if not all_templates:
                wizard.jet_template_message = _(
                    "No jet templates are currently configured as 'Show in Wizard'."
                    " Please check your jet template settings."
                )
                wizard.jet_template_domain = all_templates_domain
                continue
            if not wizard.server_id:
                # All templates that can be shown in the create wizard
                jet_template_message = False
                jet_template_domain = all_templates_domain
            else:
                # All templates that can be shown in the create wizard and
                # are installed on the selected server
                jet_template_domain = [
                    ("show_in_create_wizard", "=", True),
                    ("server_ids", "in", wizard.server_id.ids),
                ]
                available_templates = all_templates.filtered_domain(jet_template_domain)
                if not available_templates:
                    jet_template_message = _(
                        "No jet templates configured as 'Show in Wizard' are"
                        " installed on the selected server."
                        " Please check your jet template settings."
                    )
                else:
                    jet_template_message = False

            # Set the domain and message
            wizard.jet_template_domain = jet_template_domain
            wizard.jet_template_message = jet_template_message

    @api.depends("jet_template_id")
    def _compute_server_domain(self):
        """
        Compute the domain for the servers
        """
        for wizard in self:
            if not wizard.jet_template_id:
                wizard.server_domain = []
                continue
            wizard.server_domain = [("id", "in", wizard.jet_template_id.server_ids.ids)]

    @api.depends("jet_template_id")
    def _compute_state_domain(self):
        """
        Compute the domain for the states
        """
        for wizard in self:
            if not wizard.jet_template_id:
                wizard.state_domain = []
                continue
            wizard.state_domain = [
                ("id", "in", wizard.jet_template_id.action_ids.state_to_id.ids)
            ]

    def action_confirm(self):
        """
        Create a new jet
        """
        self.ensure_one()

        # Check if server is selected
        if not self.server_id:
            raise ValidationError(_("Please select a server to create a jet."))

        kwargs = {}

        # Add custom variables
        variable_values = {}
        if self.use_custom_variables == "y" and self.line_ids:
            variable_values = {
                line.variable_id.reference: line.value_char for line in self.line_ids
            }
            kwargs["variable_values"] = variable_values

        # Add partner
        if self.partner_id:
            kwargs["partner_id"] = self.partner_id.id

        # Add url
        if self.url_type == "m" and self.url:
            kwargs["url"] = self.url

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


class CxTowerJetCreateWizardVariableLine(models.TransientModel):
    """Custom variable values for jet create wizard"""

    _name = "cx.tower.jet.create.wizard.variable.line"
    _inherit = "cx.tower.custom.variable.value.mixin"
    _description = "Variable lines"

    wizard_id = fields.Many2one("cx.tower.jet.create.wizard")
    # Override from mixin to make variable_id editable
    variable_id = fields.Many2one(
        readonly=False,
    )
