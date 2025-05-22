from odoo import _, api, fields, models


class CxTowerJetTemplateInstall(models.Model):
    """Used to track installation of Jet Templates.

    Args:
        models (_type_): _description_
    """

    _name = "cx.tower.jet.template.install"
    _description = "Jet Template Install/Uninstall"

    template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        help="Tem",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        help="Server to install/uninstall the template on",
    )
    action = fields.Selection(
        selection=[("i", "Install"), ("u", "Uninstall")],
        default="i",
    )
    date_done = fields.Datetime(string="Completed on", readonly=True)
    line_ids = fields.One2many(
        comodel_name="cx.tower.jet.template.install.line",
        inverse_name="jet_template_install_id",
        auto_join=True,
        string="Templates to install",
        help="Complete list of templates to install/uninstall including dependencies",
    )
    template_to_install_ids = fields.Many2many(
        comodel_name="cx.tower.jet.template",
        relation="cx_tower_jet_template_install_to_install_rel",
        column1="template_install_id",
        column2="jet_template_id",
        help="Template to install",
    )
    template_installed_ids = fields.Many2many(
        comodel_name="cx.tower.jet.template",
        relation="cx_tower_jet_template_install_installed_rel",
        column1="template_install_id",
        column2="jet_template_id",
        help="Already installed templates",
    )
    current_template_installing_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        string="Currently Installing",
        help="Template currently being installed",
    )

    state = fields.Selection(
        selection=[("i", "Installing"), ("d", "Done"), ("f", "Failed")],
        default="i",
    )

    @api.depends("create_date", "date_done")
    def _compute_display_name(self):
        """Compute the display name of the record."""
        for record in self:
            if record.date_done:
                record.display_name = f"{str(record.date_done)}"
            else:
                record.display_name = f"{str(record.create_date)}"

    @api.model
    def install(self, server, template):
        """Install the template on the server.

        Args:
            server (cx.tower.server()): The server to install the template on.
            template (cx.tower.jet.template()): The template to install.
        """

        # Compose the list of templates to install
        template_to_install = template | template._check_dependency_satisfaction(server)

        # Prepare the list of templates to install
        template_to_install_lines = []
        order = 0
        for t in template_to_install:
            template_to_install_lines.append(
                (0, 0, {"jet_template_id": t.id, "order": order})
            )
            order += 1

        # Create a new install record
        install_record = self.create(
            {
                "template_id": template.id,
                "server_id": server.id,
                "line_ids": template_to_install_lines,
                "action": "i",
            }
        )

        # Launch the installation
        install_record._process_install()

    def _process_install(self):
        """
        Process the installation of the template.
        """
        self.ensure_one()

        # We are not using `while` because flight plans
        # may run asynchronously and we don't want to
        # block the execution of the function

        # Check if job is already done
        if self.state != "i":
            return

        # Get the template to install
        templates_to_install = self.template_to_install_ids
        if not templates_to_install:
            self.write(
                {
                    "state": "d",
                    "date_done": fields.Datetime.now(),
                    "current_template_installing_id": False,
                }
            )
            return

        # Get the last template to install
        template_to_install = templates_to_install[-1]

        # Get the flight plan to install the template
        flight_plan = template_to_install.plan_install_id  # pylint: disable=no-member
        if flight_plan:
            # Update the current template installing
            self.write(
                {
                    "current_template_installing_id": template_to_install.id,
                }
            )

            # Compose the params
            params = {
                "jet_template_install_id": self.id,  # pylint: disable=no-member
            }
            # Run the flight plan
            self.server_id.run_flight_plan(
                flight_plan=flight_plan,
                jet_template=template_to_install,
                **{"plan_log": params},
            )
            return

        # Remove the template from the list of templates to install
        # and add it to the list of installed templates
        self.write(
            {
                "template_to_install_ids": [(3, template_to_install.id)],
                "template_installed_ids": [(4, template_to_install.id)],
                "current_template_installing_id": template_to_install.id,
            }
        )

        # Add the server to the list of servers installed on the template
        template_to_install.write(
            {
                "server_ids": [(4, self.server_id.id)],
            }
        )

        # Process the installation of the template
        self._process_install()

    def _flight_plan_finished(self, jet_template, plan_status):
        """_summary_

        Args:
            jet_template (cx.tower.jet.template()): The template the plan was run for.
            exit_code (int): The exit code of the flight plan.
        """
        self.ensure_one()

        # Flight plan finished successfully
        if plan_status == 0:
            # Remove the template from the list of templates to install
            values = {
                "template_to_install_ids": [(3, jet_template.id)],
                "template_installed_ids": [(4, jet_template.id)],
            }

            # Add the server to the list of servers installed on the template
            jet_template.write(
                {
                    "server_ids": [(4, self.server_id.id)],
                }
            )
        else:
            # Mark the installation as failed
            values = {
                "state": "f",
                "date_done": fields.Datetime.now(),
            }

        # Update the installation record
        self.write(values)

        # Process the installation
        self._process_install()

    def action_view_flight_plan_logs(self):
        """Open flight plan logs related to this installation"""
        self.ensure_one()

        return {
            "name": _("Flight Plan Logs - %s", self.template_id.name),
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.plan.log",
            "view_mode": "tree,form",
            "domain": [("jet_template_install_id", "=", self.id)],
        }
