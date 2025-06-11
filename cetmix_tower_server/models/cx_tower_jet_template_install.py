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
    current_line_id = fields.Many2one(
        comodel_name="cx.tower.jet.template.install.line",
        string="Currently Installing",
        help="Line that is currently being installed",
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
        # Pick the templates with no state
        for template_line in self.line_ids.sorted("order", reverse=True):
            if template_line.state != "t":
                continue

            # Get the flight plan to install the template
            flight_plan = template_line.jet_template_id.plan_install_id  # pylint: disable=no-member

            # Run the corresponding flight plan
            if flight_plan:
                # Update the current template installing
                self.write(
                    {
                        "current_line_id": template_line.id,
                    }
                )

                # Compose the params
                params = {
                    "jet_template_install_id": self.id,  # pylint: disable=no-member
                }
                # Run the flight plan
                self.server_id.run_flight_plan(
                    flight_plan=flight_plan,
                    jet_template=template_line.jet_template_id,
                    **{"plan_log": params},
                )
                return

            # Mark the template as installed if no flight plan
            template_line.write(
                {
                    "state": "d",
                }
            )

    def _flight_plan_finished(self, plan_status):
        """
        Triggered when a flight plan that is used for installing/uninstalling
        a template is finished.

        Args:
            exit_code (int): The exit code of the flight plan.
        """
        self.ensure_one()

        # Flight plan finished successfully
        if plan_status == 0:
            # Mark current line as done
            self.current_line_id.write(
                {
                    "state": "d",
                }
            )

            # Continue the installation
            self._process_install()
        else:
            # Mark current line as failed
            self.current_line_id.write(
                {
                    "state": "f",
                }
            )

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
