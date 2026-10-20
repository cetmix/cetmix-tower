# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import yaml

from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon

from .yaml_export_check import assert_yaml_export_attributes


class TestYamlFlatExport(BaseCommon):
    """Flat YAML export and the import rules that follow it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Command = cls.env["cx.tower.command"]
        cls.Plan = cls.env["cx.tower.plan"]
        cls.JetTemplate = cls.env["cx.tower.jet.template"]
        cls.Shortcut = cls.env["cx.tower.shortcut"]
        cls.state_running = cls.env["cx.tower.jet.state"].get_by_reference("running")
        cls.state_other = cls.env["cx.tower.jet.state"].create(
            {"name": "YAML Flat Other", "reference": "yaml_flat_other"}
        )

    def _export(self, records, include_related=True):
        """Export records and return the file text and the parsed document.

        Args:
            records (recordset): Records to export. They share one model.
            include_related (bool): Wizard checkbox.

        Returns:
            tuple: YAML text and the parsed document.
        """
        wizard = (
            self.env["cx.tower.yaml.export.wiz"]
            .with_context(
                active_model=records._name,
                active_ids=records.ids,
            )
            .create({"include_related_records": include_related})
        )
        wizard.onchange_include_related_records()
        return wizard.yaml_code, yaml.safe_load(wizard.yaml_code)

    def _import(self, yaml_code, mode):
        """Import a YAML file in the given existing-record mode.

        Args:
            yaml_code (str): File contents.
            mode (str): ``skip``, ``update`` or ``create``.

        Returns:
            dict: Result action.
        """
        wizard = self.env["cx.tower.yaml.import.wiz"].create({"if_record_exists": mode})
        wizard.yaml_code = yaml_code
        return wizard.action_import_yaml()

    def _template(self, reference, requires=None, state=None):
        """Create a jet template and its dependency rows.

        Args:
            reference (str): Template reference.
            requires (recordset | None): Templates this one depends on.
            state (recordset | None): Required state. Defaults to running.

        Returns:
            recordset: Jet template.
        """
        template = self.JetTemplate.create({"name": reference, "reference": reference})
        required_state = state or self.state_running
        if requires:
            template.template_requires_ids = [
                (
                    0,
                    0,
                    {
                        "template_required_id": required.id,
                        "state_required_id": required_state.id,
                    },
                )
                for required in requires
            ]
        return template

    def test_yaml_export_attribute_registry(self):
        """Every YAML model uses a mode string on relations and True on scalars."""
        assert_yaml_export_attributes(
            self,
            [
                "cx.tower.command",
                "cx.tower.plan",
                "cx.tower.plan.line",
                "cx.tower.plan.line.action",
                "cx.tower.jet.template",
                "cx.tower.jet.waypoint.template",
                "cx.tower.server",
                "cx.tower.key",
                "cx.tower.file.template",
                "cx.tower.shortcut",
            ],
        )

    def test_export_chain_dependencies_first(self):
        """A → B → C is written C, then B, then A, and only A is a root."""
        template_c = self._template("yaml_flat_c")
        template_b = self._template("yaml_flat_b", template_c)
        template_a = self._template("yaml_flat_a", template_b)
        _code, data = self._export(template_a)
        templates = [
            record
            for record in data["records"]
            if record["cetmix_tower_model"] == "jet_template"
        ]
        self.assertEqual(
            [record["reference"] for record in templates],
            ["yaml_flat_c", "yaml_flat_b", "yaml_flat_a"],
        )
        self.assertTrue(templates[-1]["cetmix_tower_root"])
        self.assertFalse(templates[0].get("cetmix_tower_root"))
        self.assertFalse(templates[1].get("cetmix_tower_root"))

    def test_export_shared_dependency_once(self):
        """A dependency used by two selected records is written once, first."""
        template_d = self._template("yaml_flat_d")
        template_b = self._template("yaml_flat_shared_b", template_d)
        template_c = self._template("yaml_flat_shared_c", template_d)
        _code, data = self._export(template_b | template_c)
        references = [record["reference"] for record in data["records"]]
        self.assertEqual(references[0], "yaml_flat_d")
        self.assertEqual(references.count("yaml_flat_d"), 1)
        roots = [
            record["reference"]
            for record in data["records"]
            if record.get("cetmix_tower_root")
        ]
        self.assertEqual(roots, ["yaml_flat_shared_b", "yaml_flat_shared_c"])

    def test_export_plan_lists_command_before_plan(self):
        """A plan's command is a separate record, written before the plan."""
        command = self.Command.create(
            {"name": "YAML Flat Command", "reference": "yaml_flat_command"}
        )
        plan = self.Plan.create(
            {
                "name": "YAML Flat Plan",
                "reference": "yaml_flat_plan",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        _code, data = self._export(plan)
        self.assertEqual(
            [record["reference"] for record in data["records"]],
            ["yaml_flat_command", "yaml_flat_plan"],
        )
        self.assertEqual(
            data["records"][1]["line_ids"][0]["command_id"], "yaml_flat_command"
        )
        self.assertTrue(data["records"][1]["cetmix_tower_root"])
        self.assertFalse(data["records"][0].get("cetmix_tower_root"))

    def test_export_key_order(self):
        """Roots start with the model, the root marker, reference and name."""
        command = self.Command.create(
            {"name": "YAML Flat Order", "reference": "yaml_flat_order"}
        )
        _code, data = self._export(command)
        record = data["records"][0]
        self.assertEqual(
            list(record)[:4],
            ["cetmix_tower_model", "cetmix_tower_root", "reference", "name"],
        )
        self.assertEqual(record["access_level"], "manager")

    def test_export_without_related_records(self):
        """The checkbox off keeps links as references and adds no records."""
        command = self.Command.create(
            {"name": "YAML Flat Alone", "reference": "yaml_flat_alone"}
        )
        plan = self.Plan.create(
            {
                "name": "YAML Flat Alone Plan",
                "reference": "yaml_flat_alone_plan",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        _code, data = self._export(plan, include_related=False)
        self.assertEqual(
            [record["reference"] for record in data["records"]],
            ["yaml_flat_alone_plan"],
        )
        self.assertEqual(
            data["records"][0]["line_ids"][0]["command_id"], "yaml_flat_alone"
        )

    def test_cycle_export_and_import(self):
        """A cycle is written as a later reference and imports into an empty set.

        The command points at a template whose flight plan runs that command.
        Flight plans cannot run themselves, so the cycle stays across records.
        """
        command = self.Command.create(
            {
                "name": "YAML Flat Cycle",
                "reference": "yaml_flat_cycle_cmd",
                "action": "ssh_command",
            }
        )
        plan = self.Plan.create(
            {
                "name": "YAML Flat Cycle Plan",
                "reference": "yaml_flat_cycle_plan",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        template = self.JetTemplate.create(
            {
                "name": "YAML Flat Cycle Template",
                "reference": "yaml_flat_cycle_tmpl",
                "plan_install_id": plan.id,
            }
        )
        command.jet_template_id = template
        code, data = self._export(command)
        self.assertEqual(
            [record["reference"] for record in data["records"]],
            [
                "yaml_flat_cycle_plan",
                "yaml_flat_cycle_tmpl",
                "yaml_flat_cycle_cmd",
            ],
        )
        template.unlink()
        plan.unlink()
        command.unlink()
        self._import(code, "create")
        restored_command = self.Command.get_by_reference("yaml_flat_cycle_cmd")
        restored_plan = self.Plan.get_by_reference("yaml_flat_cycle_plan")
        self.assertEqual(
            restored_command.jet_template_id.plan_install_id, restored_plan
        )
        self.assertEqual(restored_plan.line_ids.command_id, restored_command)

    def test_skip_does_not_rewrite_existing_dependency(self):
        """Skip leaves an existing template's dependency when another file uses it."""
        docker = self._template("yaml_flat_docker")
        traefik = self._template("yaml_flat_traefik", docker)
        odoo = self._template(
            "yaml_flat_odoo",
            traefik | docker,
            state=self.state_other,
        )
        # Odoo requires Traefik in the other state and Docker in running,
        # so the two Traefik rows are not the same dependency.
        odoo_docker = odoo.template_requires_ids.filtered(
            lambda row: row.template_required_id == docker
        )
        odoo_docker.state_required_id = self.state_running
        code, _data = self._export(odoo)
        traefik_dependency = traefik.template_requires_ids
        # The file still names the exported reference. The database row
        # uses another one, so a reference match cannot find it.
        traefik_dependency.reference = "yaml_flat_traefik_docker_db"
        odoo.unlink()
        self._import(code, "skip")
        self.assertEqual(traefik.template_requires_ids, traefik_dependency)
        self.assertEqual(traefik_dependency.reference, "yaml_flat_traefik_docker_db")
        self.assertEqual(traefik.template_requires_ids.template_required_id, docker)
        restored = self.JetTemplate.get_by_reference("yaml_flat_odoo")
        self.assertEqual(
            set(restored.template_requires_ids.template_required_id),
            {traefik, docker},
        )

    def test_update_reimport_keeps_template_dependency(self):
        """Updating a template does not rewrite or duplicate its dependency row."""
        docker = self._template("yaml_flat_update_docker")
        traefik = self._template("yaml_flat_update_traefik", docker)
        code, _data = self._export(traefik)
        dependency = traefik.template_requires_ids
        self._import(code, "update")
        self.assertEqual(traefik.template_requires_ids, dependency)
        self.assertEqual(len(traefik.template_requires_ids), 1)

    def test_create_copies_roots_and_reuses_others(self):
        """Create copies the selected plan and reuses the command it links to."""
        command = self.Command.create(
            {"name": "YAML Flat Reused", "reference": "yaml_flat_reused"}
        )
        plan = self.Plan.create(
            {
                "name": "YAML Flat Copied",
                "reference": "yaml_flat_copied",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        code, _data = self._export(plan)
        self._import(code, "create")
        plans = self.Plan.search([("name", "=", plan.name)])
        self.assertEqual(len(plans), 2)
        new_plan = plans - plan
        self.assertNotEqual(new_plan.reference, plan.reference)
        self.assertEqual(new_plan.line_ids.command_id, command)
        self.assertEqual(
            self.Command.search_count([("reference", "=", command.reference)]), 1
        )
        self.assertEqual(command.name, "YAML Flat Reused")

    def test_create_reference_map_uses_new_root(self):
        """A later link to a copied root uses the new record, not the old one."""
        command = self.Command.create(
            {
                "name": "YAML Flat Map",
                "reference": "yaml_flat_map_cmd",
                "action": "ssh_command",
            }
        )
        plan = self.Plan.create(
            {
                "name": "YAML Flat Map Plan",
                "reference": "yaml_flat_map_plan",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        template = self.JetTemplate.create(
            {
                "name": "YAML Flat Map Template",
                "reference": "yaml_flat_map_tmpl",
                "plan_install_id": plan.id,
            }
        )
        command.jet_template_id = template
        code, _data = self._export(command)
        template.unlink()
        plan.unlink()
        self._import(code, "create")
        new_command = self.Command.search([("name", "=", command.name)]) - command
        self.assertEqual(len(new_command), 1)
        self.assertEqual(new_command.jet_template_id.reference, "yaml_flat_map_tmpl")
        self.assertEqual(
            new_command.jet_template_id.plan_install_id.line_ids.command_id,
            new_command,
        )

    def test_create_without_root_marker_copies_every_record(self):
        """A file with no root marker treats every top-level record as a root."""
        first = self.Command.create(
            {"name": "YAML Flat Unmarked 1", "reference": "yaml_flat_unmarked_1"}
        )
        second = self.Command.create(
            {"name": "YAML Flat Unmarked 2", "reference": "yaml_flat_unmarked_2"}
        )
        _code, data = self._export(first | second)
        for record in data["records"]:
            record.pop("cetmix_tower_root", None)
        self._import(yaml.dump(data, sort_keys=False), "create")
        self.assertEqual(self.Command.search_count([("name", "=", first.name)]), 2)
        self.assertEqual(self.Command.search_count([("name", "=", second.name)]), 2)

    def test_plan_line_action_imports_into_empty_database(self):
        """A plan line's actions are created with the line."""
        command = self.Command.create(
            {"name": "YAML Flat Action Command", "reference": "yaml_flat_action_cmd"}
        )
        plan = self.Plan.create(
            {
                "name": "YAML Flat Action Plan",
                "reference": "yaml_flat_action_plan",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "command_id": command.id,
                            "action_ids": [
                                (
                                    0,
                                    0,
                                    {
                                        "condition": "==",
                                        "value_char": "0",
                                        "action": "n",
                                    },
                                )
                            ],
                        },
                    )
                ],
            }
        )
        action = plan.line_ids.action_ids
        code, _data = self._export(plan)
        plan.unlink()
        command.unlink()
        self._import(code, "create")
        restored = self.Plan.get_by_reference("yaml_flat_action_plan")
        self.assertEqual(len(restored.line_ids), 1)
        self.assertEqual(len(restored.line_ids.action_ids), 1)
        self.assertEqual(restored.line_ids.action_ids.condition, "==")
        self.assertEqual(restored.line_ids.action_ids.value_char, "0")
        self.assertFalse(action.exists())

    def test_create_keeps_original_plan_line_action(self):
        """Copying a plan does not move its line actions onto the new plan."""
        command = self.Command.create(
            {"name": "YAML Flat Move Command", "reference": "yaml_flat_move_cmd"}
        )
        plan = self.Plan.create(
            {
                "name": "YAML Flat Move Plan",
                "reference": "yaml_flat_move_plan",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "command_id": command.id,
                            "action_ids": [
                                (
                                    0,
                                    0,
                                    {
                                        "condition": "==",
                                        "value_char": "0",
                                        "action": "n",
                                    },
                                )
                            ],
                        },
                    )
                ],
            }
        )
        action = plan.line_ids.action_ids
        code, _data = self._export(plan)
        self._import(code, "create")
        plans = self.Plan.search([("name", "=", plan.name)])
        self.assertEqual(len(plans), 2)
        new_plan = plans - plan
        self.assertEqual(action.line_id, plan.line_ids)
        self.assertEqual(len(new_plan.line_ids.action_ids), 1)
        self.assertNotEqual(new_plan.line_ids.action_ids, action)

    def test_waypoints_round_trip(self):
        """A template keeps every waypoint, on update and on a fresh import."""
        template = self.JetTemplate.create(
            {"name": "YAML Flat Waypoints", "reference": "yaml_flat_waypoints"}
        )
        waypoint_model = self.env["cx.tower.jet.waypoint.template"]
        waypoint_model.create(
            [
                {
                    "name": "YAML Flat WP A",
                    "reference": "yaml_flat_wp_a",
                    "jet_template_id": template.id,
                    "sequence": 1,
                },
                {
                    "name": "YAML Flat WP B",
                    "reference": "yaml_flat_wp_b",
                    "jet_template_id": template.id,
                    "sequence": 2,
                },
            ]
        )
        code, _data = self._export(template)
        self._import(code, "update")
        self.assertEqual(
            set(template.waypoint_template_ids.mapped("reference")),
            {"yaml_flat_wp_a", "yaml_flat_wp_b"},
        )
        template.unlink()
        self._import(code, "create")
        restored = self.JetTemplate.get_by_reference("yaml_flat_waypoints")
        self.assertEqual(
            set(restored.waypoint_template_ids.mapped("reference")),
            {"yaml_flat_wp_a", "yaml_flat_wp_b"},
        )

    def test_import_result_lists_each_model_once(self):
        """The mixed-model notification names each model once."""
        commands = self.Command.create(
            [
                {"name": "YAML Flat Notify 1", "reference": "yaml_flat_notify_1"},
                {"name": "YAML Flat Notify 2", "reference": "yaml_flat_notify_2"},
                {"name": "YAML Flat Notify 3", "reference": "yaml_flat_notify_3"},
            ]
        )
        plan = self.Plan.create(
            {"name": "YAML Flat Notify Plan", "reference": "yaml_flat_notify_plan"}
        )
        wizard = self.env["cx.tower.yaml.import.wiz"].create({})
        action = wizard._import_result_action([*commands, plan])
        message = action["params"]["message"]
        self.assertEqual(message.count("Cetmix Tower Command"), 1)
        self.assertEqual(message.count("Cetmix Tower Flight Plan"), 1)

    def test_skip_links_nested_variable_value_for_new_task(self):
        """A new task can use a variable value nested under a skipped template."""
        variable = self.env["cx.tower.variable"].create(
            {"name": "YAML Flat Skip Variable", "variable_type": "s"}
        )
        template = self.env["cx.tower.server.template"].create(
            {"name": "YAML Flat Skip Template", "reference": "yaml_flat_skip_tmpl"}
        )
        variable_value = self.env["cx.tower.variable.value"].create(
            {
                "variable_id": variable.id,
                "value_char": "18.0",
                "server_template_id": template.id,
                "reference": "yaml_flat_skip_value",
            }
        )
        command = self.Command.create(
            {"name": "YAML Flat Skip Command", "reference": "yaml_flat_skip_cmd"}
        )
        task = self.env["cx.tower.scheduled.task"].create(
            {
                "name": "YAML Flat Skip Task",
                "reference": "yaml_flat_skip_task",
                "action": "command",
                "command_id": command.id,
                "server_template_ids": [(4, template.id)],
                "custom_variable_value_ids": [
                    (0, 0, {"variable_value_id": variable_value.id})
                ],
            }
        )
        code, _data = self._export(template)
        task.unlink()
        self._import(code, "skip")
        restored = self.env["cx.tower.scheduled.task"].get_by_reference(
            "yaml_flat_skip_task"
        )
        self.assertEqual(
            restored.custom_variable_value_ids.variable_value_id, variable_value
        )

    def test_required_forward_reference_does_not_reuse_existing_record(self):
        """A required link to a later root is not filled from the old record."""
        state = self.env["cx.tower.jet.state"].create(
            {"name": "YAML Flat Required State", "reference": "yaml_flat_req_state"}
        )
        yaml_code = """
cetmix_tower_yaml_version: 1
records:
- cetmix_tower_model: jet_action
  reference: yaml_flat_req_action
  name: YAML Flat Required Action
  access_level: manager
  state_transit_id: yaml_flat_req_state
- cetmix_tower_model: jet_state
  cetmix_tower_root: true
  reference: yaml_flat_req_state
  name: YAML Flat Required State
  access_level: manager
"""
        with self.assertRaises(ValidationError) as error:
            self._import(yaml_code, "create")
        self.assertIn("Deferred relation resolution failed", str(error.exception))
        self.assertIn("yaml_flat_req_state", str(error.exception))
        self.assertFalse(
            self.env["cx.tower.jet.action"].get_by_reference("yaml_flat_req_action")
        )
        self.assertEqual(
            self.env["cx.tower.jet.state"].get_by_reference("yaml_flat_req_state"),
            state,
        )

    def test_forward_reference_outside_old_allow_list(self):
        """A shortcut can link to a flight plan that appears later in the file."""
        yaml_code = """
cetmix_tower_yaml_version: 1
records:
- cetmix_tower_model: shortcut
  cetmix_tower_root: true
  reference: yaml_flat_shortcut
  name: YAML Flat Shortcut
  action: plan
  access_level: manager
  plan_id: yaml_flat_shortcut_plan
- cetmix_tower_model: plan
  reference: yaml_flat_shortcut_plan
  name: YAML Flat Shortcut Plan
  access_level: manager
"""
        self._import(yaml_code, "skip")
        shortcut = self.Shortcut.get_by_reference("yaml_flat_shortcut")
        plan = self.Plan.get_by_reference("yaml_flat_shortcut_plan")
        self.assertEqual(shortcut.plan_id, plan)
