# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models

from odoo.addons.cetmix_tower_server.models.constants import FILE_CREATION_FAILED

_logger = logging.getLogger(__name__)


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    git_project_rel_ids = fields.One2many(
        comodel_name="cx.tower.git.project.rel",
        inverse_name="server_id",
        copy=False,
        depends=["git_project_ids"],
        groups="cetmix_tower_base.group_manager,cetmix_tower_base.group_root",
        help="Legacy: Git Projects linked through files on this server."
        " Kept for servers that do not use Jets. New setups should link"
        " the Git Project to the Jet and write it with Upload Git Project.",
    )

    # Helper field to get all git projects related to server
    # IMPORTANT: This field may contain duplicates because of the relation nature!
    git_project_ids = fields.Many2many(
        comodel_name="cx.tower.git.project",
        relation="cx_tower_git_project_rel",
        column1="server_id",
        column2="git_project_id",
        readonly=True,
        copy=False,
        depends=["git_project_rel_ids"],
        groups="cetmix_tower_base.group_manager,cetmix_tower_base.group_root",
        help="Legacy: Git Projects linked through files on this server."
        " Kept for servers that do not use Jets.",
    )

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "git_project_rel_ids",
        ]
        return res

    def _get_force_x2m_resolve_models(self):
        res = super()._get_force_x2m_resolve_models()

        # Add File in order to always try to use existing one
        res += ["cx.tower.file"]
        return res

    def _update_or_create_related_record(
        self, model, reference, values, create_immediately=False
    ):
        # Files must be created immediately because they are related
        # to both server and git project.
        # So if a file is not created immediately when it is created
        # for the server, the same file will be created for the git project.
        # This will lead to creation of two files with the same content
        # for the same server.

        if model._name == "cx.tower.file":
            create_immediately = True
        return super()._update_or_create_related_record(
            model, reference, values, create_immediately=create_immediately
        )

    @api.model
    def get_servers_by_git_ref(self, repository_url, head=None, head_type=None):
        """
        Return servers linked to a given Git repository reference.

        Legacy: kept for servers that do not use Jets. New setups should
        link the Git Project to the Jet and write it with Upload Git
        Project.

        Parameters
        ----------
        repository_url : str
            Pre-normalized canonical Git URL
            (e.g. ``https://host/owner/repo.git``).
        head : str, optional
            Branch name, commit SHA, or PR identifier.
        head_type : {'branch', 'commit', 'pr'}, optional
            Type of the ``head`` argument.
            If only ``head`` is provided, it will match across all head types.
            If only ``head_type`` is provided, it will filter by type regardless of head

        Returns
        -------
        recordset of cx.tower.server
            Matching servers. Empty recordset if no matches.
        """

        server_obj = self.env["cx.tower.server"]
        # URL MUST be already canonical.
        if not repository_url:
            return server_obj

        # Get repository id by URL
        repo_id = self.env["cx.tower.git.repo"]._get_repo_id_by_url(
            repository_url, raise_if_invalid=False
        )
        if not repo_id:
            return server_obj
        repo = self.env["cx.tower.git.repo"].browse(repo_id)

        # Compose domain for remotes
        remote_domain = [
            ("source_id.enabled", "=", True),
            ("enabled", "=", True),
        ]
        if head:
            head = self.env["cx.tower.git.remote"]._sanitize_head(head)
            remote_domain.append(("head", "=", head))
        if head_type:
            remote_domain.append(("head_type", "=", head_type))

        # Get remotes
        remotes = repo.remote_ids.filtered_domain(remote_domain)
        if not remotes:
            return server_obj

        # Get servers from remotes
        servers = remotes.mapped("git_project_id.git_project_rel_ids.server_id")
        return servers

    def _command_runner_file_using_template_create_file(
        self,
        log_record,
        server_dir,
        **kwargs,
    ):
        """Override to create git project relation
        when creating a file using a template.
        """
        file = super()._command_runner_file_using_template_create_file(
            log_record, server_dir, **kwargs
        )
        if file:
            # Get the flight plan line from log record
            plan_line = log_record.plan_log_id.plan_line_executed_id
            # Try to get git project from custom values
            custom_values = log_record.variable_values
            git_project_reference = custom_values and custom_values.get(
                "__git_project__"
            )
            if git_project_reference:
                git_project = self.env["cx.tower.git.project"].get_by_reference(
                    git_project_reference
                )
                if not git_project:
                    _logger.warning(
                        "Git project '%s' provided with the `__git_project__` "
                        "custom value not found for server '%s' "
                        "in flight plan line '%s' "
                        "of the flight plan '%s'. "
                        "No project was linked to the file '%s'.",
                        git_project_reference,
                        self.name,
                        plan_line.name,
                        log_record.plan_log_id.plan_id.name,
                        file.name,
                    )

            # Try to get git project set explicitly in the flight plan line
            else:
                git_project = plan_line.git_project_id
            if not git_project:
                return file

            if plan_line.is_make_copy:
                # Remove default_server_ids from context, because this relation
                # will be created through git_project_rel_ids.
                # default_server_ids will interfere at the moment when
                # pairs of values are created through SQL query
                # in the method write_real and it does not take into account
                # that in this case we are creating a copy of the git project
                git_project = git_project.with_context(default_server_ids=False).copy(
                    {"name": git_project._compose_copy_name(server=self)}
                )

            self.env["cx.tower.git.project.rel"].create(
                {
                    "git_project_id": git_project.id,
                    "server_id": self.id,
                    "file_id": file.id,
                    "project_format": git_project._default_project_format(),
                }
            )
        return file

    def _get_command_runners(self):
        """Register the Upload Git Project command runner.

        Returns:
            dict: Command action to runner method.
        """
        runners = super()._get_command_runners()
        runners["git_project_upload"] = self._command_runner_git_project_upload
        return runners

    def _command_runner_git_project_upload(
        self,
        command,
        log_record,
        rendered_command_code=None,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Write the Jet's Git Project to a file on the Jet's server.

        Args:
            command (cx.tower.command): Command being run.
            log_record (cx.tower.command.log): Command log, if any.
            rendered_command_code (str, optional): Rendered command code.
            sudo (str, optional): Command sudo mode.
            rendered_command_path (str, optional): Rendered directory path.
            ssh_connection: SSH connection to reuse.
            **kwargs: Extra arguments.

        Returns:
            dict | None: Command result when there is no log record.
        """
        try:
            jet = log_record.jet_id if log_record else self.env["cx.tower.jet"]
            if not jet or not jet.git_project_id:
                return self._git_project_upload_finish(
                    log_record,
                    status=0,
                    response=_("No Git Project to upload"),
                )

            file_name = self._render_git_file_name(command, jet)
            server_dir = self.env["cx.tower.file"]._sanitize_values(
                {"server_dir": rendered_command_path or ""}
            )["server_dir"]
            # Match cx.tower.file full_server_path, including an empty directory.
            full_path = f"{server_dir}/{file_name}"

            file_model = self.env["cx.tower.file"]
            candidates = file_model.search(
                [
                    ("jet_id", "=", jet.id),
                    ("source", "=", "tower"),
                ]
            )
            files = candidates.filtered(lambda rec: rec.full_server_path == full_path)
            file = files[:1]

            if not file:
                file = file_model.create(
                    {
                        "name": command.git_file_name,
                        "server_dir": server_dir,
                        "server_id": jet.server_id.id,
                        "jet_id": jet.id,
                        "source": "tower",
                        "file_type": "text",
                        "auto_sync": False,
                    }
                )

            project = jet.git_project_id
            project_format = project._default_project_format()
            rel_model = self.env["cx.tower.git.project.rel"]
            link = rel_model.search(
                [
                    ("git_project_id", "=", project.id),
                    ("file_id", "=", file.id),
                    ("project_format", "=", project_format),
                ],
                limit=1,
            )
            if link:
                link._save_to_file()
            else:
                rel_model.create(
                    {
                        "git_project_id": project.id,
                        "server_id": jet.server_id.id,
                        "file_id": file.id,
                        "project_format": project_format,
                    }
                )

            if not file.auto_sync:
                file.auto_sync = True
            file.action_push_to_server()
            return self._git_project_upload_finish(
                log_record,
                status=0,
                response=_("Git Project uploaded successfully"),
            )
        except Exception as err:  # pylint: disable=broad-exception-caught
            _logger.exception(
                "Git Project upload failed for command '%s' on server '%s'.",
                command.name,
                self.name,
            )
            return self._git_project_upload_finish(
                log_record,
                status=FILE_CREATION_FAILED,
                error=_("An error occurred: %(error)s", error=str(err)),
            )

    def _render_git_file_name(self, command, jet):
        """Render ``git_file_name`` the same way the file model renders
        ``name``.

        Args:
            command (cx.tower.command): Command with ``git_file_name``.
            jet (cx.tower.jet): Jet the command runs on.

        Returns:
            str: Rendered file name, or the raw name when there are no
                variable values.
        """
        raw_name = command.git_file_name or ""
        references = command.get_variables_from_code(raw_name)
        if not references:
            return raw_name
        values = self.env["cx.tower.variable"]._get_variable_values_by_references(
            references,
            server=jet.server_id,
            jet_template=jet.jet_template_id,
            jet=jet,
        )
        if not values:
            return raw_name
        return command.render_code_custom(raw_name, **values)

    def _git_project_upload_finish(
        self, log_record, status=0, response=None, error=None
    ):
        """Finish the command log or return a result dict.

        Args:
            log_record (cx.tower.command.log): Log record, if any.
            status (int): Command status.
            response (str, optional): Success message.
            error (str, optional): Error message.

        Returns:
            dict | None: Result when there is no log record.
        """
        if log_record:
            log_record.finish(
                finish_date=fields.Datetime.now(),
                status=status,
                response=response,
                error=error,
            )
            return None
        return {"status": status, "response": response, "error": error}
