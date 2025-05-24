from odoo import fields, models


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

    state = fields.Selection(
        selection=[("i", "Installing"), ("d", "Done"), ("f", "Failed")],
        default="i",
    )

    def install(self, server, template):
        """Install the template on the server.

        Args:
            server (cx.tower.server()): The server to install the template on.
            template (cx.tower.jet.template()): The template to install.
        """

        # Compose the list of templates to install
        template_to_install = template | template._check_dependency_satisfaction(server)

        # Create a new install record
        install_record = self.create(
            {
                "template_id": template.id,
                "server_id": server.id,
                "template_to_install_ids": [(4, t.id) for t in template_to_install],
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
                }
            )
            return

        # Get the last template to install
        template_to_install = templates_to_install[-1]

        # Get the flight plan to install the template
        flight_plan = template_to_install.plan_install_id  # pylint: disable=no-member
        if flight_plan:
            # Compose the params
            params = {
                "jet_template_action": "i",
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
