# Copyright (C) 2026 Crumges
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class CxTowerJetCreateWizard(models.TransientModel):
    _inherit = "cx.tower.jet.create.wizard"

    @api.onchange("jet_template_id", "use_custom_variables")
    def _onchange_jet_template_id_populate_variables(self):
        """
        Loads the configuration variables defined in the selected Jet Template
        into the wizard's line_ids when custom settings are chosen.
        """
        if not self.jet_template_id:
            self.line_ids = [(5, 0, 0)]
            self.use_custom_variables = "n"
            return

        if self.use_custom_variables == "n":
            self.line_ids = [(5, 0, 0)]
            return

        # If custom settings are selected, populate lines if they are empty
        # or if the template changed (the variables in lines don't belong
        # to the template)
        template_var_ids = set(
            self.jet_template_id.variable_value_ids.mapped("variable_id.id")
        )
        line_var_ids = set(self.line_ids.mapped("variable_id.id"))

        if not self.line_ids or (line_var_ids != template_var_ids):
            lines = []
            for val in self.jet_template_id.variable_value_ids:
                lines.append(
                    (
                        0,
                        0,
                        {
                            "variable_id": val.variable_id.id,
                            "value_char": val.value_char,
                            "option_id": val.option_id.id
                            if hasattr(val, "option_id") and val.option_id
                            else False,
                            "variable_value_id": val.id,
                        },
                    )
                )
            self.line_ids = [(5, 0, 0)] + lines
