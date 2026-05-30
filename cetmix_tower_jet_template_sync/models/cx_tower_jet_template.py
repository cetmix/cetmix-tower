# Copyright (C) 2026 Crumges
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class CxTowerJetTemplate(models.Model):
    _inherit = "cx.tower.jet.template"

    has_pending_sync = fields.Boolean(
        compute="_compute_has_pending_sync",
    )

    @api.depends(
        "jet_ids",
        "jet_ids.variable_value_ids",
        "jet_ids.server_log_ids",
        "jet_ids.scheduled_task_ids",
        "jet_ids.exclude_from_sync",
        "variable_value_ids",
        "server_log_ids",
        "scheduled_task_ids",
    )
    def _compute_has_pending_sync(self):
        all_jets = self.mapped("jet_ids").filtered(lambda j: not j.exclude_from_sync)
        if all_jets:
            all_jets.mapped("variable_value_ids")
            all_jets.mapped("server_log_ids")
            all_jets.mapped("scheduled_task_ids")

        for template in self:
            pending = False
            jets = template.jet_ids.filtered(lambda j: not j.exclude_from_sync)
            if jets:
                # 1. Check if any variable from template is missing in any jet
                template_var_ids = set(
                    template.variable_value_ids.mapped("variable_id.id")
                )
                for jet in jets:
                    jet_var_ids = set(jet.variable_value_ids.mapped("variable_id.id"))
                    if not template_var_ids.issubset(jet_var_ids):
                        pending = True
                        break

                if not pending:
                    # 2. Check if any log from template (by name) is missing in any jet
                    template_log_names = set(template.server_log_ids.mapped("name"))
                    for jet in jets:
                        jet_log_names = set(jet.server_log_ids.mapped("name"))
                        if not template_log_names.issubset(jet_log_names):
                            pending = True
                            break

                if not pending:
                    # 3. Check if any scheduled task from template is missing in any jet
                    template_task_ids = set(template.scheduled_task_ids.ids)
                    for jet in jets:
                        jet_task_ids = set(jet.scheduled_task_ids.ids)
                        if not template_task_ids.issubset(jet_task_ids):
                            pending = True
                            break

            template.has_pending_sync = pending

    def _prepare_jet_values(self, server, name=None, **kwargs):
        """
        Extends the standard preparation of Jet values to ensure that
        variables defined on the template are also physically copied (propagated)
        to the Jet record, unless they were already overridden by the user.
        """
        vals = super()._prepare_jet_values(server, name=name, **kwargs)

        existing_vars = vals.get("variable_value_ids", [])
        existing_var_ids = set()
        for cmd in existing_vars:
            if isinstance(cmd, tuple | list) and cmd[0] == 0:
                existing_var_ids.add(cmd[2].get("variable_id"))

        new_vars = list(existing_vars)
        for template_val in self.variable_value_ids:
            if template_val.variable_id.id not in existing_var_ids:
                new_vars.append(
                    (
                        0,
                        0,
                        {
                            "variable_id": template_val.variable_id.id,
                            "value_char": template_val.value_char,
                            "option_id": template_val.option_id.id
                            if template_val.option_id
                            else False,
                        },
                    )
                )

        if new_vars:
            vals["variable_value_ids"] = new_vars

        return vals

    def action_sync_to_jets(self):
        """
        Synchronizes variables, logs, and scheduled tasks from the template
        to all its existing Jets.
        - Variables: Only adds variables that do not already exist on the Jet.
        - Logs: Only adds server logs that do not already exist on the Jet
          (by name).
        - Scheduled Tasks: Only adds scheduled tasks that do not already
          exist on the Jet.
        """
        self.ensure_one()
        jets = self.jet_ids.filtered(lambda j: not j.exclude_from_sync)
        if not jets:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sync Complete"),
                    "message": _("No non-excluded jets found for this template."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # 1. Sync Variables
        template_vars = self.variable_value_ids
        value_obj = self.env["cx.tower.variable.value"]
        vars_created_count = 0

        if template_vars:
            # Prefetch variable values for all jets in one go
            jets.mapped("variable_value_ids")
            existing_vars_by_jet = {
                jet.id: set(jet.variable_value_ids.mapped("variable_id.id"))
                for jet in jets
            }
            vars_to_create = []
            for jet in jets:
                existing_var_ids = existing_vars_by_jet[jet.id]
                to_sync_vars = template_vars.filtered(
                    lambda v, var_ids=existing_var_ids: v.variable_id.id not in var_ids
                )
                for template_val in to_sync_vars:
                    vars_to_create.append(
                        {
                            "variable_id": template_val.variable_id.id,
                            "value_char": template_val.value_char,
                            "option_id": template_val.option_id.id
                            if template_val.option_id
                            else False,
                            "jet_id": jet.id,
                        }
                    )
            if vars_to_create:
                value_obj.create(vars_to_create)
                vars_created_count = len(vars_to_create)

        # 2. Sync Logs
        logs_created_count = 0
        template_logs = self.server_log_ids
        if template_logs:
            # Prefetch server logs for all jets in one go
            jets.mapped("server_log_ids")
            existing_logs_by_jet = {
                jet.id: set(jet.server_log_ids.mapped("name")) for jet in jets
            }
            for jet in jets:
                existing_log_names = existing_logs_by_jet[jet.id]
                to_sync_logs = template_logs.filtered(
                    lambda log, log_names=existing_log_names: log.name not in log_names
                )
                for template_log in to_sync_logs:
                    jet_log = template_log.copy(
                        {
                            "jet_id": jet.id,
                            "server_id": jet.server_id.id,
                            "jet_template_id": False,
                        }
                    )
                    if (
                        template_log.log_type == "file"
                        and template_log.file_template_id
                    ):
                        jet_log.file_id = template_log.file_template_id.create_file(
                            server=jet.server_id, jet=jet, if_file_exists="skip"
                        ).id
                    logs_created_count += 1

        # 3. Sync Scheduled Tasks
        tasks_created_count = 0
        template_tasks = self.scheduled_task_ids
        if template_tasks:
            # Prefetch scheduled tasks for all jets in one go
            jets.mapped("scheduled_task_ids")
            for jet in jets:
                missing_tasks = template_tasks - jet.scheduled_task_ids
                if missing_tasks:
                    jet.scheduled_task_ids = [(4, task.id) for task in missing_tasks]
                    tasks_created_count += len(missing_tasks)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sync Complete"),
                "message": _(
                    "Successfully synchronized to %(jets)d jet(s):\n"
                    "- %(vars)d variable(s)\n"
                    "- %(logs)d log(s)\n"
                    "- %(tasks)d scheduled task(s)",
                    jets=len(jets),
                    vars=vars_created_count,
                    logs=logs_created_count,
                    tasks=tasks_created_count,
                ),
                "type": "success",
                "sticky": False,
            },
        }
