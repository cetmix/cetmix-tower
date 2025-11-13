import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class CxTowerJetTemplateInstall(models.Model):
    """
    Used to track installation of Jet Templates on servers.
    """

    _name = "cx.tower.jet.template.install"
    _description = "Jet Template Install/Uninstall"
    _order = "create_date desc"
    _rec_name = "jet_template_id"

    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        required=True,
        help="Template to install/uninstall",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        index=True,
        ondelete="cascade",
        required=True,
        help="Server to install/uninstall the template on",
    )
    action = fields.Selection(
        selection=[("install", "Install"), ("uninstall", "Uninstall")],
        default="install",
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
        selection=[
            ("processing", "Processing"),
            ("installed", "Installed"),
            ("failed", "Failed"),
        ],
        default="processing",
        index=True,
    )

    @api.model
    def install(self, server, template):
        """Install the template on the server.

        Args:
            server (cx.tower.server()): The server to install the template on.
            template (cx.tower.jet.template()): The template to install.
        """

        # Compose the list of templates to install
        template_to_install = [template] + template._check_dependency_satisfaction(
            server
        )

        # Prepare the template install lines
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
        if self.state != "processing":
            return

        # Exit if there are some lines currently being installed
        if self.current_line_id:
            return

        # Get the template to install
        installation_tasks = self.line_ids.sorted("order", reverse=True)
        for installation_task in installation_tasks:
            # Pick the templates only in the "To Install" state
            if installation_task.state != "to_install":
                continue

            # Get the flight plan to install the template
            flight_plan = installation_task.jet_template_id.plan_install_id  # pylint: disable=no-member

            # Run the corresponding flight plan
            if flight_plan:
                # Update the current template install line
                self.write(
                    {
                        "current_line_id": installation_task.id,
                    }
                )
                # WARNING: Explicit commit to ensure visibility across transactions
                # This prevents race conditions in async flight plan callbacks
                with self.env.cr.savepoint():
                    # Add the install record to the flight plan params
                    params = {
                        "jet_template_install_id": self.id,  # pylint: disable=no-member
                    }
                    # Run the flight plan
                    self.server_id.run_flight_plan(
                        flight_plan=flight_plan,
                        jet_template=installation_task.jet_template_id,
                        **{"plan_log": params},
                    )
                    # Flight plan will trigger the `_process_install` function again
                    # if the flight plan is finished successfully.
                    # So we don't need continue the loop in this case.
                    return

            # Mark the installation task as "Installed"
            # because nothing else is to be done here.
            installation_task.write(
                {
                    "state": "installed",
                }
            )
            # Add to the list of installed templates
            installation_task.jet_template_id.write(
                {"server_ids": [(4, self.server_id.id)]}
            )

        # Mark the installation as done
        self.write(
            {
                "state": "installed",
                "date_done": fields.Datetime.now(),
            }
        )

        # Savepoint to ensure that the installation is marked as done
        # even if the next action fails.
        with self.env.cr.savepoint():
            return

    def _flight_plan_finished(self, plan_status):
        """
        Triggered when a flight plan that is used for installing/uninstalling
        a template is finished.

        Args:
            plan_status (int): The exit code of the flight plan.
        """
        self.ensure_one()

        # Validate callback state
        if not self.current_line_id:
            _logger.warning(
                "Callback invoked with no current_line_id for install %s", self.id
            )
            return

        if self.state != "processing":
            _logger.warning(
                "Callback invoked for install %s in state %s", self.id, self.state
            )
            return

        # Flight plan finished successfully
        if plan_status == 0:
            # Mark current line as done
            self.current_line_id.write(  # pylint: disable=no-member
                {
                    "state": "installed",
                }
            )
            # Add template to the list of installed templates
            self.current_line_id.jet_template_id.write(  # pylint: disable=no-member
                {"server_ids": [(4, self.server_id.id)]}
            )

            # Remove the link to the current line and continue
            self.write({"current_line_id": False})
            self._process_install()
        else:
            # Mark current line as failed
            self.current_line_id.write(  # pylint: disable=no-member
                {
                    "state": "failed",
                }
            )
            # Clear the current line link
            self.write(
                {
                    "state": "failed",
                    "date_done": fields.Datetime.now(),
                    "current_line_id": False,
                }
            )

    def action_view_flight_plan_logs(self):
        """Open flight plan logs related to this installation"""
        self.ensure_one()

        return {
            "name": _(
                "Flight Plan Logs - %(install_name)s",
                install_name=self.jet_template_id.name,
            ),
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.plan.log",
            "view_mode": "tree,form",
            "domain": [("jet_template_install_id", "=", self.id)],  # pylint: disable=no-member
        }
