# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

REPO_LINE_KEYS = {
    "remote_id",
    "repo_id",
    "repo_reference",
    "repo_url",
    "head_type",
    "head",
    "url_protocol",
    "enabled",
    "source",
}
REPO_HEAD_TYPES = {"branch", "pr", "commit"}
REPO_URL_PROTOCOLS = {"ssh", "https", "git"}


class CxTowerGitProject(models.Model):
    """
    Git Project.
    Implements pre-defined git configuration.
    """

    _name = "cx.tower.git.project"
    _description = "Cetmix Tower Git Project"
    _order = "name"

    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.yaml.mixin",
        "cx.tower.access.role.mixin",
    ]

    def _get_post_create_fields(self):
        res = super()._get_post_create_fields()
        return res + [
            "source_ids",
            "git_project_rel_ids",
        ]

    active = fields.Boolean(default=True)
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_git_project_server_rel",
        readonly=True,
        copy=False,
        compute="_compute_server_ids",
        store=True,
        context={"active_test": False},
        help="Servers are added automatically based on the files"
        " linked to the project. Legacy: used for servers that do not"
        " use Jets. New setups should link the Git Project to the Jet.",
    )
    jet_ids = fields.One2many(
        comodel_name="cx.tower.jet",
        inverse_name="git_project_id",
        string="Jets",
        readonly=True,
        copy=False,
        context={"active_test": False},
    )
    source_ids = fields.One2many(
        comodel_name="cx.tower.git.source",
        inverse_name="git_project_id",
        string="Sources",
        auto_join=True,
        copy=True,
    )
    git_project_rel_ids = fields.One2many(
        comodel_name="cx.tower.git.project.rel",
        inverse_name="git_project_id",
        string="Git Project Server File Relations",
        copy=False,
    )
    # Helper field to get all files related to git project
    file_ids = fields.Many2many(
        comodel_name="cx.tower.file",
        relation="cx_tower_git_project_rel",
        column1="git_project_id",
        column2="file_id",
        string="Files",
        readonly=True,
        depends=["git_project_rel_ids"],
        copy=False,
    )
    # Helper field to get all repositories used in this project
    repo_ids = fields.Many2many(
        comodel_name="cx.tower.git.repo",
        relation="cx_tower_git_repo_project_rel",
        column1="project_id",
        column2="repo_id",
        string="Repositories",
        readonly=True,
        copy=False,
        help="Repositories used in this project through its sources and remotes",
    )
    note = fields.Text()

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_git_project_user_rel",
        compute="_compute_user_ids",
        readonly=False,
        store=True,
        precompute=True,
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_git_project_manager_rel",
        compute="_compute_user_ids",
        readonly=False,
        store=True,
        precompute=True,
    )

    # -- UI/UX fields
    has_private_remotes = fields.Boolean(
        compute="_compute_has_private_remotes",
        help="Indicates if the project has any private remotes.",
    )
    has_partially_private_remotes = fields.Boolean(
        compute="_compute_has_private_remotes",
        help="Indicates if the project has any partially private remotes.",
    )

    # -- Git Aggregator related fields
    git_aggregator_root_dir = fields.Char(
        help="Git aggregator root directory where sources will be cloned."
        " Eg '/tmp/git-aggregator'"
        " Will use '.' if not set",
    )

    def _selection_project_format(self):
        """
        Possible project formats.
        Inherit and extend when adding new project formats.

        Returns:
            List of tuples: (code, name)
        """
        return [
            ("git_aggregator", "Git Aggregator"),
        ]

    def _default_project_format(self):
        """
        Default project format.
        """
        return "git_aggregator"

    @api.depends("git_project_rel_ids", "git_project_rel_ids.server_id")
    def _compute_server_ids(self):
        """Compute server ids for git projects.

        Why? Because a git project can be linked to multiple files
        on the same server.
        So we need to use a set to avoid duplicates so every server
        is listed only once.
        """
        for project in self:
            project.server_ids = (
                list(set(project.git_project_rel_ids.server_id.ids))
                if project.git_project_rel_ids
                else False
            )

    @api.depends(
        "git_project_rel_ids.server_id",
        "git_project_rel_ids.server_id.user_ids",
        "git_project_rel_ids.server_id.manager_ids",
    )
    def _compute_user_ids(self):
        """
        Users. All users who have "Manager" group and are either set in "Users"
        or in "Managers" in all related servers.
        Managers. All users who have "Manager" group and are set as "Managers"
        in all related servers.

        This is done to avoid unpredictable consequences when some of the servers
        are not updated due to access restrictions when a project is updated.
        """
        for project in self:
            # Do not compute if no servers are related
            server_ids = project.git_project_rel_ids.server_id
            if not server_ids:
                continue

            # Get all user and manager ids from related servers
            all_user_ids = server_ids.user_ids.filtered(
                lambda u: u.has_group("cetmix_tower_base.group_manager")
            ).ids
            all_manager_ids = server_ids.manager_ids.ids

            # Create a final list of user and manager ids
            user_ids = []
            manager_ids = []
            # Check if user is present in all servers
            for user_id in all_user_ids:
                if all(
                    user_id in server.user_ids.ids or user_id in server.manager_ids.ids
                    for server in server_ids
                ):
                    user_ids.append(user_id)
            # Check if manager is present in all servers
            for manager_id in all_manager_ids:
                if all(manager_id in server.manager_ids.ids for server in server_ids):
                    manager_ids.append(manager_id)

            # Set the final lists
            project.update(
                {
                    "user_ids": [(6, 0, user_ids)],
                    "manager_ids": [(6, 0, manager_ids)],
                }
            )

    @api.depends(
        "source_ids", "source_ids.remote_ids", "source_ids.remote_ids.is_private"
    )
    def _compute_has_private_remotes(self):
        for project in self:
            project.has_private_remotes = any(
                source.remote_count > 0
                and source.remote_count_private == source.remote_count
                for source in project.source_ids
            )
            project.has_partially_private_remotes = any(
                source.remote_count_private > 0
                and source.remote_count_private != source.remote_count
                for source in project.source_ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Update related files and templates on create
        res._update_related_files_and_templates()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Update related files and templates on update
        self._update_related_files_and_templates()
        return res

    def unlink(self):
        """Unlink remotes and sources before the project.

        ``source.git_project_id`` and ``remote.git_project_id`` both
        CASCADE. Odoo ``unlink`` still issues a SQL ``DELETE`` of the
        project, so PostgreSQL would drop those rows without calling
        Python ``unlink`` on remotes and sources. Those overrides
        refresh related aggregator files.
        """
        self.source_ids.remote_ids.unlink()
        self.source_ids.unlink()
        return super().unlink()

    # ------------------------------
    # Helper methods
    # ------------------------------
    def _update_related_files_and_templates(self):
        # Update related files and templates
        if self.git_project_rel_ids:
            self.git_project_rel_ids._save_to_file()

    def _extract_variables_from_text(self, text):
        """Extract environment variables from text.
        Helper method for file content generation.

        Args:
            text (str): Text to extract variables from
        Returns:
            List: List of variables
        """
        # This regex will find all variables where variables are denoted
        # as $VAR or ${VAR}, e.g., $FOO or ${FOO_BAR123}
        variables = re.findall(r"\$\{?([A-Z0-9_]+)\}?", text)
        return sorted(list(set(variables)))

    def _compose_copy_name(self, server=False):
        """
        Compose copy name of a git project copy.
        Helper method used when creating a copy of a git project.

        Args:
            server (cx.tower.server): Server to get the copy name for.

        Returns:
            Char: Copy name
        """
        self.ensure_one()
        if server:
            return server.name
        return _("%(name)s (copy)", name=self.name)

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "note",
            "source_ids",
            "git_aggregator_root_dir",
        ]
        return res

    # -------------------------------
    # Git Aggregator related methods
    # -------------------------------
    def _git_aggregator_prepare_record(self):
        """Prepare json structure for git aggregator.

        Returns:
            Dict: Json structure for git aggregator
        """
        self.ensure_one()
        values = {}
        sources = self.source_ids.sorted(
            key=lambda source: (source.sequence, source.name or "", source.id)
        )
        for source in sources:
            if source.enabled and source.remote_count:
                root_dir = self.git_aggregator_root_dir or "."
                values.update(
                    {
                        f"/{source.reference}"
                        if root_dir == "/"
                        else f"{root_dir}/{source.reference}": source._git_aggregator_prepare_record()  # noqa: E501
                    }
                )
        return values

    def _git_aggregator_prepare_yaml_comment(self, yaml_code):
        """Generate commentary for yaml file.
        It includes brief instructions for git aggregator
        and lists environment variables that are required.

        Args:
            yaml_code (str): Yaml code

        Returns:
            Char: comment text or None
        """

        comment_text = _(
            "# This file is generated with Cetmix Tower https://cetmix.com/tower\n"
            "# It's designed to be used with git-aggregator tool developed by Acsone.\n"
            "# Documentation for git-aggregator: https://github.com/acsone/git-aggregator\n"
        )
        variable_list = self._extract_variables_from_text(yaml_code)
        if variable_list:
            comment_text += _(
                "\n# You need to set the following variables in your environment:\n# %(vars)s\n"  # noqa: E501
                "# and run git-aggregator with '--expand-env' parameter.\n",  # noqa: E501
                vars=(", ".join(variable_list)),
            )
        return comment_text

    def _generate_code_git_aggregator(self, record):
        """Generate code in git-aggregator format.

        Args:
            record (recordset()): Model record to generate code for.
                must be a single record and have git_project_id field.

        Returns:
            Text: Yaml code
        """
        yaml_mixin = self.env["cx.tower.yaml.mixin"]

        # Do not generate code if record values are empty
        record_values = record.git_project_id._git_aggregator_prepare_record()
        if record_values:
            yaml_code = yaml_mixin._convert_dict_to_yaml(record_values)
            # Prepend comment to yaml code
            comment = record.git_project_id._git_aggregator_prepare_yaml_comment(
                yaml_code
            )
            return f"{comment}\n{yaml_code}"
        return ""

    # ------------------------------
    # Repo lines (flat list API)
    # ------------------------------
    def get_repo_lines(self):
        """Return remotes as a list of dicts in flat-list order.

        Each dict has ``remote_id``, ``repo_id``, ``repo_reference``,
        ``repo_url``, ``head_type``, ``head``, ``url_protocol``,
        ``enabled`` and read-only ``source`` (source name).

        Returns:
            list: Repo line dicts. Never ``None``.
        """
        self.ensure_one()
        lines = []
        for remote in self._get_flat_remotes():
            lines.append(
                {
                    "remote_id": remote.id,
                    "repo_id": remote.repo_id.id,
                    "repo_reference": remote.repo_id.reference or "",
                    "repo_url": remote.repo_id.url or "",
                    "head_type": remote.head_type,
                    "head": remote.head or "",
                    "url_protocol": remote.url_protocol,
                    "enabled": bool(remote.enabled),
                    "source": remote.source_id.name or "",
                }
            )
        return lines

    def add_repo_lines(self, lines):
        """Append repo lines using grouping rules G1, G2 and G5.

        Args:
            lines (list): List of repo line dicts.

        Returns:
            bool: Always ``True``.
        """
        self.ensure_one()
        parsed = self._parse_repo_lines(lines)
        for line in parsed:
            self._create_remote_from_line(line)
        return True

    def set_repo_lines(self, lines):
        """Make this project's remotes exactly ``lines``.

        Matching rule, applied in list order, each existing remote
        matched at most once:

        1. A line with ``remote_id`` matches that remote. The id must
           belong to this project and must not already be matched.
        2. A line without ``remote_id`` matches the first still-unmatched
           remote, in flat-list order, with the same repository,
           ``head_type`` and ``head``.
        3. Unmatched lines create remotes. Unmatched remotes are deleted.

        Args:
            lines (list): List of repo line dicts.

        Returns:
            bool: Always ``True``.
        """
        self.ensure_one()
        parsed = self._parse_repo_lines(lines)
        remotes = self._get_flat_remotes()
        matched_ids = set()
        ordered = []
        for index, line in enumerate(parsed):
            remote = self._match_repo_line(line, remotes, matched_ids, index)
            if remote:
                matched_ids.add(remote.id)
                self._write_remote_from_line(remote, line)
            else:
                remote = self._create_remote_from_line(line)
                remotes |= remote
                matched_ids.add(remote.id)
            ordered.append(remote)
        (remotes - remotes.browse(list(matched_ids))).unlink()
        self._delete_empty_sources()
        self._apply_flat_order(ordered)
        return True

    def _get_flat_remotes(self):
        """Return remotes in flat-list order.

        Returns:
            recordset: ``cx.tower.git.remote`` records.
        """
        self.ensure_one()
        remotes = self.source_ids.mapped("remote_ids")
        return remotes.sorted(
            key=lambda remote: (
                remote.source_id.sequence,
                remote.source_id.name or "",
                remote.sequence,
                remote.name or "",
                remote.id,
            )
        )

    def _parse_repo_lines(self, lines):
        """Validate and normalise repo line dicts.

        Args:
            lines (list): Raw repo line dicts.

        Returns:
            list: Parsed dicts with a resolved ``repo`` record.

        Raises:
            ValidationError: If a line is invalid. The message names
                the line index.
        """
        if lines is None:
            lines = []
        if not isinstance(lines, list):
            raise ValidationError(_("Repo lines must be a list of dictionaries."))
        parsed = []
        for index, line in enumerate(lines):
            if not isinstance(line, dict):
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: expected a dictionary.",
                        index=index,
                    )
                )
            unknown = set(line) - REPO_LINE_KEYS
            if unknown:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: unknown key '%(key)s'.",
                        index=index,
                        key=sorted(unknown)[0],
                    )
                )
            head_type = line.get("head_type")
            if not head_type:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: missing head_type.",
                        index=index,
                    )
                )
            if head_type not in REPO_HEAD_TYPES:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: invalid head_type"
                        " '%(head_type)s'.",
                        index=index,
                        head_type=head_type,
                    )
                )
            head = line.get("head")
            if not head:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: missing head.",
                        index=index,
                    )
                )
            head = self.env["cx.tower.git.remote"]._sanitize_head(head)
            url_protocol = line.get("url_protocol") or "https"
            if url_protocol not in REPO_URL_PROTOCOLS:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: invalid url_protocol"
                        " '%(url_protocol)s'.",
                        index=index,
                        url_protocol=url_protocol,
                    )
                )
            enabled = line["enabled"] if "enabled" in line else True
            remote_id = line.get("remote_id")
            if remote_id:
                try:
                    remote_id = int(remote_id)
                except (TypeError, ValueError) as err:
                    raise ValidationError(
                        _(
                            "Invalid repo line %(index)s: invalid remote_id.",
                            index=index,
                        )
                    ) from err
            repo = self._resolve_repo_from_line(line, index)
            parsed.append(
                {
                    "remote_id": remote_id or False,
                    "repo": repo,
                    "head_type": head_type,
                    "head": head,
                    "url_protocol": url_protocol,
                    "enabled": bool(enabled),
                }
            )
        return parsed

    def _resolve_repo_from_line(self, line, index):
        """Resolve the repository from ``repo_id``, ``repo_reference``
        and/or ``repo_url``.

        Args:
            line (dict): Repo line dict.
            index (int): Line index for error messages.

        Returns:
            recordset: Single ``cx.tower.git.repo``.

        Raises:
            ValidationError: If no key is given, a key cannot be
                resolved, or keys disagree.
        """
        repo_model = self.env["cx.tower.git.repo"]
        resolved = self.env["cx.tower.git.repo"]
        if line.get("repo_id"):
            try:
                repo_id = int(line["repo_id"])
            except (TypeError, ValueError) as err:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: invalid repo_id.",
                        index=index,
                    )
                ) from err
            repo = repo_model.browse(repo_id)
            if not repo.exists():
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: repository id"
                        " %(repo_id)s was not found.",
                        index=index,
                        repo_id=repo_id,
                    )
                )
            resolved |= repo
        if line.get("repo_reference"):
            repo = repo_model.get_by_reference(line["repo_reference"])
            if not repo:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: unresolvable"
                        " repository reference '%(reference)s'.",
                        index=index,
                        reference=line["repo_reference"],
                    )
                )
            resolved |= repo
        if line.get("repo_url"):
            repo_id = repo_model._get_repo_id_by_url(
                line["repo_url"], create=True, raise_if_invalid=True
            )
            if not repo_id:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: invalid URL.",
                        index=index,
                    )
                )
            resolved |= repo_model.browse(repo_id)
        if not resolved:
            raise ValidationError(
                _(
                    "Invalid repo line %(index)s: missing repository"
                    " (repo_id, repo_reference or repo_url).",
                    index=index,
                )
            )
        if len(resolved) > 1:
            raise ValidationError(
                _(
                    "Invalid repo line %(index)s: repository keys resolve"
                    " to different repositories.",
                    index=index,
                )
            )
        return resolved

    def _match_repo_line(self, line, remotes, matched_ids, index):
        """Return the existing remote that matches ``line``, if any.

        Args:
            line (dict): Parsed repo line.
            remotes (recordset): Current project remotes.
            matched_ids (set): Remote ids already matched.
            index (int): Line index for error messages.

        Returns:
            recordset: Matching remote or empty.

        Raises:
            ValidationError: If ``remote_id`` is invalid.
        """
        if line.get("remote_id"):
            remote = remotes.filtered(lambda rec: rec.id == line["remote_id"])
            if not remote:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: remote_id %(remote_id)s"
                        " does not belong to this project.",
                        index=index,
                        remote_id=line["remote_id"],
                    )
                )
            if remote.id in matched_ids:
                raise ValidationError(
                    _(
                        "Invalid repo line %(index)s: remote_id %(remote_id)s"
                        " is used twice.",
                        index=index,
                        remote_id=line["remote_id"],
                    )
                )
            return remote
        for remote in remotes:
            if remote.id in matched_ids:
                continue
            if (
                remote.repo_id == line["repo"]
                and remote.head_type == line["head_type"]
                and remote.head == line["head"]
            ):
                return remote
        return self.env["cx.tower.git.remote"]

    def _find_source_for_repo(self, repo, exclude_remote=None):
        """Return the source that already has a remote of ``repo``.

        When several sources contain the repository, use the first by
        ``sequence, name`` (G2).

        Args:
            repo (cx.tower.git.repo): Repository.
            exclude_remote (cx.tower.git.remote, optional): Remote to
                ignore so a repository change does not match its current
                source.

        Returns:
            recordset: Matching source or empty.
        """
        self.ensure_one()
        exclude = exclude_remote or self.env["cx.tower.git.remote"]
        sources = self.source_ids.filtered(
            lambda source: repo in (source.remote_ids - exclude).repo_id
        ).sorted(key=lambda source: (source.sequence, source.name or ""))
        return sources[:1]

    def _get_or_create_source_for_repo(self, repo, exclude_remote=None):
        """Return the source for ``repo``, creating one if needed (G1).

        Args:
            repo (cx.tower.git.repo): Repository.
            exclude_remote (cx.tower.git.remote, optional): Remote to
                ignore when looking up an existing source.

        Returns:
            recordset: ``cx.tower.git.source``.
        """
        self.ensure_one()
        source = self._find_source_for_repo(repo, exclude_remote=exclude_remote)
        if source:
            return source
        return self.env["cx.tower.git.source"].create(
            {
                "git_project_id": self.id,
                "sequence": self._next_source_sequence(),
            }
        )

    def _next_source_sequence(self):
        """Return the sequence for a new source appended at the end.

        Returns:
            int: Next source sequence.
        """
        self.ensure_one()
        sequences = self.source_ids.mapped("sequence")
        return (max(sequences) + 10) if sequences else 10

    def _next_remote_sequence(self, source):
        """Return the sequence for a remote appended to ``source`` (G5).

        Args:
            source (cx.tower.git.source): Source.

        Returns:
            int: Next remote sequence.
        """
        sequences = source.remote_ids.mapped("sequence")
        return (max(sequences) + 10) if sequences else 10

    def _create_remote_from_line(self, line):
        """Create a remote from a parsed repo line (G1, G2, G5).

        Args:
            line (dict): Parsed repo line.

        Returns:
            recordset: Created ``cx.tower.git.remote``.
        """
        self.ensure_one()
        source = self._get_or_create_source_for_repo(line["repo"])
        remote = self.env["cx.tower.git.remote"].create(
            {
                "source_id": source.id,
                "repo_id": line["repo"].id,
                "head_type": line["head_type"],
                "head": line["head"],
                "url_protocol": line["url_protocol"],
                "enabled": line["enabled"],
                "sequence": self._next_remote_sequence(source),
            }
        )
        source._compose_name_if_placeholder()
        return remote

    def _write_remote_from_line(self, remote, line):
        """Write parsed line values onto ``remote``.

        A repository change moves the same record (G3).

        Args:
            remote (cx.tower.git.remote): Remote to update.
            line (dict): Parsed repo line.
        """
        vals = {
            "head_type": line["head_type"],
            "head": line["head"],
            "url_protocol": line["url_protocol"],
            "enabled": line["enabled"],
        }
        if remote.repo_id != line["repo"]:
            old_source = remote.source_id
            new_source = self._get_or_create_source_for_repo(
                line["repo"], exclude_remote=remote
            )
            vals["repo_id"] = line["repo"].id
            if new_source != old_source:
                vals["source_id"] = new_source.id
                vals["sequence"] = self._next_remote_sequence(new_source)
            remote.write(vals)
            if old_source.exists() and not old_source.remote_ids:
                old_source.unlink()
            new_source._compose_name_if_placeholder()
            return
        remote.write(vals)

    def _apply_flat_order(self, remotes):
        """Write source and remote sequences from flat-list order.

        Source order is the order of each source's first remote.
        Remote order within a source is the relative order of that
        source's remotes in ``remotes``.

        Args:
            remotes (list): Remote records in flat-list order.
        """
        source_seq = {}
        next_source = 10
        next_remote = {}
        remote_batches = {}
        remote_model = self.env["cx.tower.git.remote"]
        for remote in remotes:
            if not remote.exists():
                continue
            source = remote.source_id
            if source.id not in source_seq:
                source_seq[source.id] = next_source
                next_source += 10
                next_remote[source.id] = 10
            sequence = next_remote[source.id]
            remote_batches.setdefault(sequence, remote_model)
            remote_batches[sequence] |= remote
            next_remote[source.id] += 10
        for sequence, batch in remote_batches.items():
            batch.write({"sequence": sequence})
        for source_id, sequence in source_seq.items():
            self.env["cx.tower.git.source"].browse(source_id).write(
                {"sequence": sequence}
            )

    def _delete_empty_sources(self):
        """Delete sources that have no remotes (G4)."""
        self.ensure_one()
        self.source_ids.filtered(lambda source: not source.remote_ids).unlink()

    @api.model
    def _create_named_git_project(self, name):
        """Create a project named ``name``.

        Args:
            name (str): Project name.

        Returns:
            recordset: Created ``cx.tower.git.project``.
        """
        return self.create({"name": name})

    def _copy_named(self, name):
        """Copy this project, named exactly ``name``.

        Args:
            name (str): Name of the copy.

        Returns:
            recordset: Copied ``cx.tower.git.project``.
        """
        self.ensure_one()
        return self.with_context(reference_mixin_skip_copy=True).copy({"name": name})

    def _is_orphan_git_project(self):
        """Return whether this project can be deleted with its last Jet.

        Returns:
            bool: ``True`` if no Jet, file link or plan line uses it.
        """
        self.ensure_one()
        if self.with_context(active_test=False).jet_ids:
            return False
        if self.git_project_rel_ids:
            return False
        if self.env["cx.tower.plan.line"].search(
            [("git_project_id", "=", self.id)], limit=1
        ):
            return False
        return True
