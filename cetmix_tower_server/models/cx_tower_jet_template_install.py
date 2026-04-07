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
            ("done", "Done"),
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

        Returns:
            cx.tower.jet.template.install(): The installation record.
        """
        server.ensure_one()
        template.ensure_one()

        # Compose the list of templates to install
        # NB: templates will be installed later in reverse order
        # to ensure that dependencies are satisfied
        template_to_process = [template] + template._check_dependency_satisfaction(
            server
        )

        # Prepare the template install lines
        template_to_process_lines = []
        order = 0
        for t in template_to_process:
            template_to_process_lines.append(
                (0, 0, {"jet_template_id": t.id, "order": order})
            )
            order += 1

        # Create a new install record
        install_record = self.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "line_ids": template_to_process_lines,
            }
        )

        # Send notification
        # Action for button
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.cx_tower_jet_template_install_action"
        )

        context = self.env.context.copy()
        params = dict(context.get("params") or {})
        params["button_name"] = _("View Installation")
        context["params"] = params

        # Add record id and context to the action
        action.update(
            {
                "context": context,
                "res_id": install_record.id,
                "views": [(False, "form")],
            }
        )

        self.env.user.notify_info(
            message=_(
                "%(timestamp)s<br/>" "Installing template on server '%(server_name)s'",
                server_name=server.name,
                timestamp=fields.Datetime.context_timestamp(
                    self, fields.Datetime.now()
                ),
            ),
            title=template.name,
            sticky=False,  # explicitly set to False to avoid blocking the user's screen
            action=action,
        )

        # Launch the installation
        install_record._process_install()

        # Return the installation record
        return install_record

    @api.model
    def uninstall(self, server, template):
        """Uninstall the template from the server.
        NB: only one template can be uninstalled at a time.

        Args:
            server (cx.tower.server()): The server to uninstall the template from.
            template (cx.tower.jet.template()): The template to uninstall.
        """
        server.ensure_one()
        template.ensure_one()

        # Create a new install record
        install_record = self.create(
            {
                "jet_template_id": template.id,
                "server_id": server.id,
                "line_ids": [(0, 0, {"jet_template_id": template.id, "order": 0})],
                "action": "uninstall",
            }
        )

        # Send notification
        # Action for button
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.cx_tower_jet_template_install_action"
        )

        context = self.env.context.copy()
        params = dict(context.get("params") or {})
        params["button_name"] = _("View Installation")
        context["params"] = params

        # Add record id and context to the action
        action.update(
            {
                "context": context,
                "res_id": install_record.id,
                "views": [(False, "form")],
            }
        )

        self.env.user.notify_info(
            message=_(
                "%(timestamp)s<br/>"
                "Uninstalling template on server '%(server_name)s'",
                server_name=server.name,
                timestamp=fields.Datetime.context_timestamp(
                    self, fields.Datetime.now()
                ),
            ),
            title=template.name,
            sticky=False,  # explicitly set to False to avoid blocking the user's screen
            action=action,
        )

        # Launch the installation
        install_record._process_install()

        # Return the installation record
        return install_record

    def _process_install(self):
        """
        Process the installation or uninstallation of the template.
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
            # Pick the templates only in the "To Process" state
            if installation_task.state != "to_process":
                continue

            # Get the flight plan to install the template
            if self.action == "install":
                flight_plan = installation_task.jet_template_id.plan_install_id  # pylint: disable=no-member
            else:
                flight_plan = installation_task.jet_template_id.plan_uninstall_id  # pylint: disable=no-member

            # Run the corresponding flight plan
            if flight_plan:
                # Update the current template install line
                self.write(
                    {
                        "current_line_id": installation_task.id,
                    }
                )

                # Add the install record to the flight plan params
                plan_params = {
                    "jet_template_install_id": self.id,  # pylint: disable=no-member
                }
                with self.env.cr.savepoint():
                    # Run the flight plan (exceptions handled inside the flight plan)
                    self.server_id.run_flight_plan(
                        flight_plan=flight_plan,
                        jet_template=installation_task.jet_template_id,
                        **{"plan_log": plan_params},
                    )
                # Flight plan will trigger the `_process_install` function again
                # if the flight plan is finished successfully.
                # So we don't need continue the loop in this case.
                return

            # Mark the installation task as "Done"
            # because nothing else is to be done here.
            installation_task.write(
                {
                    "state": "done",
                }
            )
            # Add to the list of installed templates
            if self.action == "install":
                installation_task.jet_template_id.write(
                    {"server_ids": [(4, self.server_id.id)]}
                )
            else:
                installation_task.jet_template_id.write(
                    {"server_ids": [(3, self.server_id.id)]}
                )

            # Refresh the frontend views
            self.env.user.reload_views(
                model="cx.tower.jet.template.install",
                rec_ids=[self.id],
            )

        # Mark the installation as done
        now = fields.Datetime.now()
        self.write(
            {
                "state": "done",
                "date_done": now,
            }
        )

        # Refresh the frontend views
        self.env.user.reload_views(
            model="cx.tower.jet.template.install", rec_ids=[self.id]
        )
        self.env.user.reload_views(
            model="cx.tower.server", view_types=["form"], rec_ids=[self.server_id.id]
        )
        self.env.user.reload_views(
            model="cx.tower.jet.template",
            view_types=["form"],
            rec_ids=[self.jet_template_id.id],
        )

        # Check if notifications are enabled
        ICP_sudo = self.env["ir.config_parameter"].sudo()
        notification_type_success = ICP_sudo.get_param(
            "cetmix_tower_server.notification_type_success"
        )
        # Send notification to the user
        if notification_type_success:
            # Action for button
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "cetmix_tower_server.cx_tower_jet_template_install_action"
            )

            context = self.env.context.copy()
            params = dict(context.get("params") or {})
            params["button_name"] = _("View Installation")
            context["params"] = params

            # Add record id and context to the action
            action.update(
                {
                    "context": context,
                    "res_id": self.id,
                    "views": [(False, "form")],
                }
            )
            # Send success notification
            self.env.user.notify_success(
                message=_(
                    "%(timestamp)s<br/>"
                    "%(action)s completed on server '%(server_name)s'",
                    action=_("Installation")
                    if self.action == "install"
                    else _("Uninstallation"),
                    server_name=self.server_id.name,
                    timestamp=fields.Datetime.context_timestamp(self, now),
                ),
                title=self.jet_template_id.name,  # pylint: disable=no-member
                sticky=notification_type_success == "sticky",
                action=action,
            )

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
                    "state": "done",
                }
            )
            # Add template to the list of installed templates
            # or remove it from the list if it is being uninstalled
            if self.action == "install":
                self.current_line_id.jet_template_id.write(  # pylint: disable=no-member
                    {"server_ids": [(4, self.server_id.id)]}
                )
            else:
                self.current_line_id.jet_template_id.write(  # pylint: disable=no-member
                    {"server_ids": [(3, self.server_id.id)]}
                )

            # Remove the link to the current line and continue
            self.write({"current_line_id": False})

            # Refresh the frontend views
            self.env.user.reload_views(
                model="cx.tower.jet.template.install",
                rec_ids=[self.id],
            )
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

            # Set all other 'to_process' lines as failed
            self.line_ids.filtered(lambda line: line.state == "to_process").write(
                {
                    "state": "failed",
                }
            )

            # Refresh the frontend views
            self.env.user.reload_views(
                model="cx.tower.jet.template.install",
                rec_ids=[self.id],
            )
            # Send notification to the user
            # Check if notifications are enabled
            ICP_sudo = self.env["ir.config_parameter"].sudo()
            notification_type_error = ICP_sudo.get_param(
                "cetmix_tower_server.notification_type_error"
            )
            if notification_type_error:
                # Action for button
                action = self.env["ir.actions.act_window"]._for_xml_id(
                    "cetmix_tower_server.cx_tower_jet_template_install_action"
                )

                context = self.env.context.copy()
                params = dict(context.get("params") or {})
                params["button_name"] = _("View Installation")
                context["params"] = params

                # Add record id and context to the action
                action.update(
                    {
                        "context": context,
                        "res_id": self.id,
                        "views": [(False, "form")],
                    }
                )
                # Send error notification
                self.env.user.notify_danger(
                    message=_(
                        "%(timestamp)s<br/>"
                        "%(action)s failed on server '%(server_name)s'",
                        action=_("Installation")
                        if self.action == "install"
                        else _("Uninstallation"),
                        server_name=self.server_id.name,
                        timestamp=fields.Datetime.context_timestamp(
                            self, fields.Datetime.now()
                        ),
                    ),
                    title=self.jet_template_id.name,
                    sticky=notification_type_error == "sticky",
                    action=action,
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
            "view_mode": "list,form",
            "domain": [("jet_template_install_id", "=", self.id)],  # pylint: disable=no-member
        }
