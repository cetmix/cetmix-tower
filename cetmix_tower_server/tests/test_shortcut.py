from .common import TestTowerCommon


class TestTowerShortcut(TestTowerCommon):
    """Test Tower Shortcut"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Server
        cls.server_test_1_pro = cls.Server.create(
            {
                "name": "Test 1 Pro",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "skip_host_key": True,
            }
        )

        # Variable
        cls.variable_path_pro = cls.Variable.create({"name": "test_path_pro"})

        # Command
        cls.command_list_dir_pro = cls.Command.create(
            {
                "name": "Test create directory",
                "code": "ls -l {{ test_path_ }}",
            }
        )

        # Flight plan
        cls.plan_1_pro = cls.Plan.create(
            {
                "name": "Test plan 1 Pro",
                "note": "List directory contents",
            }
        )
        cls.plan_line_1_pro = cls.plan_line.create(
            {
                "sequence": 5,
                "plan_id": cls.plan_1_pro.id,
                "command_id": cls.command_list_dir_pro.id,
            }
        )

        # Shortcuts
        cls.shortcut_for_command = cls.Shortcut.create(
            {
                "name": "Shortcut for Command",
                "action": "command",
                "command_id": cls.command_list_dir_pro.id,
                "server_ids": [(4, cls.server_test_1_pro.id)],
            }
        )

        cls.shortcut_for_flight_plan = cls.Shortcut.create(
            {
                "name": "Shortcut for Flight Plan",
                "action": "plan",
                "plan_id": cls.plan_1_pro.id,
                "server_ids": [(4, cls.server_test_1_pro.id)],
            }
        )

    def test_shortcut_user_access_rules(self):
        """Test shortcut user access rules"""
        # Create shortcuts with different access levels and server/template assignments
        shortcut_level_1_server = self.Shortcut.create(
            {
                "name": "Level 1 Server Shortcut",
                "action": "command",
                "command_id": self.command_list_dir_pro.id,
                "server_ids": [(4, self.server_test_1_pro.id)],
                "access_level": "1",
            }
        )

        shortcut_level_2_template = self.Shortcut.create(
            {
                "name": "Level 2 Template Shortcut",
                "action": "command",
                "command_id": self.command_list_dir_pro.id,
                "server_template_ids": [(4, self.server_template_sample.id)],
                "access_level": "2",
            }
        )

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        shortcut_server_as_bob = shortcut_level_1_server.with_user(self.user_bob)
        shortcut_template_as_bob = shortcut_level_2_template.with_user(self.user_bob)

        # Test: User access
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        self.server_test_1_pro.write({"user_ids": [(4, self.user_bob.id)]})

        # User should see level 1 shortcuts for their servers
        res = shortcut_server_as_bob.read(["name"])
        self.assertEqual(res[0]["name"], shortcut_level_1_server.name)

        # User should NOT see level 2 shortcuts
        search_result = shortcut_template_as_bob.search(
            [("id", "=", shortcut_level_2_template.id)]
        )
        self.assertEqual(len(search_result), 0)

        # Test: Manager access through server assignment
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        self.server_test_1_pro.write({"manager_ids": [(4, self.user_bob.id)]})

        # Manager should see shortcuts for servers they manage
        res = shortcut_server_as_bob.read(["name"])
        self.assertEqual(res[0]["name"], shortcut_level_1_server.name)

        # Manager should NOT see template shortcuts without template access
        search_result = shortcut_template_as_bob.search(
            [("id", "=", shortcut_level_2_template.id)]
        )
        self.assertEqual(len(search_result), 0)

        # Test: Manager access through template assignment
        self.server_template_sample.write({"manager_ids": [(4, self.user_bob.id)]})

        # Manager should now see template shortcuts
        res = shortcut_template_as_bob.read(["name"])
        self.assertEqual(res[0]["name"], shortcut_level_2_template.name)

        # Test: Manager access as template user
        self.server_template_sample.write(
            {
                "manager_ids": [(3, self.user_bob.id)],  # Remove from managers
                "user_ids": [(4, self.user_bob.id)],  # Add as user
            }
        )

        # Manager should still see template shortcuts when they're a template user
        res = shortcut_template_as_bob.read(["name"])
        self.assertEqual(res[0]["name"], shortcut_level_2_template.name)

        # Test: Root access to all shortcuts
        shortcut_level_3 = self.Shortcut.create(
            {
                "name": "Level 3 Mixed Shortcut",
                "action": "command",
                "command_id": self.command_list_dir_pro.id,
                "server_ids": [(4, self.server_test_1_pro.id)],
                "server_template_ids": [(4, self.server_template_sample.id)],
                "access_level": "3",
            }
        )
        shortcut_level_3_as_bob = shortcut_level_3.with_user(self.user_bob)

        # Manager should NOT see level 3 shortcuts
        search_result = shortcut_level_3_as_bob.search(
            [("id", "=", shortcut_level_3.id)]
        )
        self.assertEqual(len(search_result), 0)

        # Root should see all shortcuts
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")
        search_result = shortcut_level_3_as_bob.search(
            [
                (
                    "id",
                    "in",
                    [
                        shortcut_level_1_server.id,
                        shortcut_level_2_template.id,
                        shortcut_level_3.id,
                    ],
                )
            ]
        )
        self.assertEqual(len(search_result), 3)

    def test_shortcut_run_type_command(self):
        """Test run shortcut of type 'command'"""
        self.shortcut_for_command.run(self.server_test_1_pro)

        # Check command log
        shortcut_result = self.CommandLog.search(
            [("command_id", "=", self.shortcut_for_command.command_id.id)]
        )
        self.assertEqual(len(shortcut_result), 1, "Must be single log record")
        self.assertEqual(
            shortcut_result.server_id,
            self.server_test_1_pro,
            "Server should match",
        )

    def test_shortcut_run_type_plan(self):
        """Test run shortcut of type 'plan'"""
        self.shortcut_for_flight_plan.run(self.server_test_1_pro)

        # Check shortcut log
        shortcut_result = self.PlanLog.search(
            [("plan_id", "=", self.shortcut_for_flight_plan.plan_id.id)]
        )
        self.assertEqual(len(shortcut_result), 1, "Must be single log record")
        self.assertEqual(
            shortcut_result.server_id,
            self.server_test_1_pro,
            "Server should match",
        )

    def test_shortcut_run_from_context(self):
        """Test running shortcut with server from context"""
        # Create a test shortcut
        shortcut = self.Shortcut.create(
            {
                "name": "Context Test Shortcut",
                "action": "command",
                "command_id": self.command_list_dir_pro.id,
                "server_ids": [(4, self.server_test_1_pro.id)],
            }
        )

        # Run with server_id in context
        shortcut.with_context(server_id=self.server_test_1_pro.id).run()

        # Check command log was created
        log_entries = self.CommandLog.search(
            [
                ("command_id", "=", shortcut.command_id.id),
                ("server_id", "=", self.server_test_1_pro.id),
            ]
        )
        self.assertEqual(len(log_entries), 1, "Should create a log entry")
        self.assertEqual(
            log_entries.server_id,
            self.server_test_1_pro,
            "Server should match",
        )
