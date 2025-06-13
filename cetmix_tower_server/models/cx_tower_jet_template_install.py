from odoo import _, api, fields, models


class CxTowerJetTemplateInstall(models.Model):
    """Used to track installation of Jet Templates.

    Args:
        models (_type_): _description_
    """

    _name = "cx.tower.jet.template.install"
    _description = "Jet Template Install/Uninstall"
    _order = "create_date desc"

    jet_template_id = fields.Many2one(
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
        selection=[("p", "Processing"), ("i", "Installed"), ("f", "Failed")],
        default="p",
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
                "jet_template_id": template.id,
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

        # Continue only if the job is still processing
        if self.state != "p":
            return

        # Exit if there are some lines currently being installed
        if self.current_line_id:
            return

        # In case no lines are to be installed, mark the job as done
        all_installed = True

        # Get the template to install
        for installation_task in self.line_ids.sorted("order", reverse=True):
            # Pick the templates only in the "To Install" state
            if installation_task.state != "t":
                continue

            # Mark the template as still to be processed
            all_installed = False

            # Get the flight plan to install the template
            flight_plan = installation_task.jet_template_id.plan_install_id  # pylint: disable=no-member

            # Run the corresponding flight plan
            if flight_plan:
                # Update the current template installing
                self.write(
                    {
                        "current_line_id": installation_task.id,
                    }
                )

                # Compose the params
                params = {
                    "jet_template_install_id": self.id,  # pylint: disable=no-member
                }
                # Run the flight plan
                self.server_id.run_flight_plan(
                    flight_plan=flight_plan,
                    jet_template=installation_task.jet_template_id,
                    **{"plan_log": params},
                )
            else:
                # Mark the template line as installed if no flight plan
                installation_task.write(
                    {
                        "state": "i",
                    }
                )
                # Add to the list of installed templates
                installation_task.jet_template_id.write(
                    {"server_ids": [(4, self.server_id.id)]}
                )
                # Continue the installation
                self._process_install()

        if all_installed:
            self.write(
                {
                    "state": "i",
                    "date_done": fields.Datetime.now(),
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
                    "state": "i",
                }
            )
            # Add template to the list of installed templates
            self.current_line_id.jet_template_id.write(
                {"server_ids": [(4, self.server_id.id)]}
            )

            # Remove the link to the current line
            self.current_line_id = False

            # Continue the installation
            self._process_install()
        else:
            # Mark current line as failed
            self.current_line_id.write(
                {
                    "state": "f",
                }
            )
            # We leave the last line link to simplify the debugging process
            self.write(
                {
                    "state": "f",
                    "date_done": fields.Datetime.now(),
                }
            )

    def action_view_flight_plan_logs(self):
        """Open flight plan logs related to this installation"""
        self.ensure_one()

        return {
            "name": _("Flight Plan Logs - %s", self.jet_template_id.name),
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.plan.log",
            "view_mode": "tree,form",
            "domain": [("jet_template_install_id", "=", self.id)],  # pylint: disable=no-member
        }
