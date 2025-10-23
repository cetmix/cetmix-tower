from .common import TestTowerCommon


class TestTowerTagMixin(TestTowerCommon):
    """Test class for tower tag mixin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create 3 tags to test tag mixin
        cls.tag_test_1 = cls.Tag.create(
            {
                "name": "Test Tag 1",
            }
        )
        cls.tag_test_2 = cls.Tag.create(
            {
                "name": "Test Tag 2",
            }
        )
        cls.tag_test_3 = cls.Tag.create(
            {
                "name": "Test Tag 3",
            }
        )

        # Create 3 commands to test tag mixin
        cls.command_test_1 = cls.Command.create(
            {
                "name": "Test Command 1",
            }
        )
        cls.command_test_2 = cls.Command.create(
            {
                "name": "Test Command 2",
            }
        )
        cls.command_test_3 = cls.Command.create(
            {
                "name": "Test Command 3",
            }
        )

        cls.all_commands = cls.command_test_1 | cls.command_test_2 | cls.command_test_3

        # Add tags to commands
        # - Command 1: Test Tag 1, Test Tag 2
        cls.command_test_1.add_tags(["Test Tag 1", "Test Tag 2", "Test Tag 3"])
        # - Command 2: Test Tag 2, Test Tag 3
        cls.command_test_2.add_tags(["Test Tag 2", "Test Tag 3"])
        # - Command 3: Test Tag 3
        cls.command_test_3.add_tags(["Test Tag 3"])

    def test_01_add_tags(self):
        """Test that tags are added to the record"""
        self.assertEqual(len(self.command_test_1.tag_ids), 3)
        self.assertEqual(len(self.command_test_2.tag_ids), 2)
        self.assertEqual(len(self.command_test_3.tag_ids), 1)
        self.assertIn(self.tag_test_1, self.command_test_1.tag_ids)
        self.assertIn(self.tag_test_2, self.command_test_1.tag_ids)
        self.assertIn(self.tag_test_3, self.command_test_1.tag_ids)
        self.assertIn(self.tag_test_2, self.command_test_2.tag_ids)
        self.assertIn(self.tag_test_3, self.command_test_2.tag_ids)
        self.assertIn(self.tag_test_3, self.command_test_3.tag_ids)

        # Test adding duplicate tags (should be idempotent)
        self.command_test_1.add_tags(["Test Tag 1"])
        self.assertEqual(len(self.command_test_1.tag_ids), 3)

        # Test adding single tag name
        self.command_test_1.add_tags("Test Tag 1")
        self.assertEqual(len(self.command_test_1.tag_ids), 3)
        self.assertIn(self.tag_test_1, self.command_test_1.tag_ids)
        self.assertIn(self.tag_test_2, self.command_test_1.tag_ids)
        self.assertIn(self.tag_test_3, self.command_test_1.tag_ids)

        # Test adding invalid type (should return True)
        self.assertTrue(self.command_test_1.add_tags(123))
        self.assertTrue(self.command_test_1.add_tags([]))
        # Test adding invalid type (should return True)
        # Empty list is a no-op
        before = len(self.command_test_1.tag_ids)
        self.assertTrue(self.command_test_1.add_tags([]))
        self.assertEqual(len(self.command_test_1.tag_ids), before)

        # Test adding non-existent tags (should be ignored)
        initial_count = len(self.command_test_1.tag_ids)
        self.command_test_1.add_tags(["Non Existent Tag"])
        self.assertEqual(len(self.command_test_1.tag_ids), initial_count)

    def test_02_remove_tags(self):
        """Test that tags are removed from the record"""
        self.command_test_1.remove_tags(["Test Tag 1", "Test Tag 2"])
        self.assertEqual(len(self.command_test_1.tag_ids), 1)

        # Test removing single tag name
        self.command_test_2.remove_tags("Test Tag 2")
        self.assertEqual(len(self.command_test_2.tag_ids), 1)
        self.assertIn(self.tag_test_3, self.command_test_2.tag_ids)

        # Test removing invalid type (should return True)
        self.assertTrue(self.command_test_1.remove_tags(123))
        # Test removing no tags (should return True)
        self.assertTrue(self.command_test_1.remove_tags([]))

    def test_03_has_tags(self):
        """Test that the record has any of the given tags"""

        # Search selected records
        commands_with_any_tags = self.all_commands.has_tags(
            ["Test Tag 1", "Test Tag 2"]
        )
        self.assertEqual(len(commands_with_any_tags), 2)
        self.assertIn(self.command_test_1, commands_with_any_tags)
        self.assertIn(self.command_test_2, commands_with_any_tags)

        # Search all records in the model
        commands_with_any_tags = self.Command.has_tags(
            ["Test Tag 1", "Test Tag 2"], search_all=True
        )
        self.assertEqual(len(commands_with_any_tags), 2)
        self.assertIn(self.command_test_1, commands_with_any_tags)
        self.assertIn(self.command_test_2, commands_with_any_tags)

        # Search with single tag name
        commands_with_any_tags = self.all_commands.has_tags("Test Tag 2")
        self.assertEqual(len(commands_with_any_tags), 2)
        self.assertIn(self.command_test_1, commands_with_any_tags)
        self.assertIn(self.command_test_2, commands_with_any_tags)

        commands_with_any_tags = self.Command.has_tags("Test Tag 2", search_all=True)
        self.assertEqual(len(commands_with_any_tags), 2)
        self.assertIn(self.command_test_1, commands_with_any_tags)
        self.assertIn(self.command_test_2, commands_with_any_tags)

        # Search with invalid type (should return empty recordset)
        commands_with_any_tags = self.Command.has_tags(123)
        self.assertEqual(len(commands_with_any_tags), 0)

        # Search with no tags (should return empty recordset)
        commands_with_any_tags = self.Command.has_tags([])
        self.assertEqual(len(commands_with_any_tags), 0)

    def test_04_has_all_tags(self):
        """Test that the record has all of the given tags"""

        # Search selected records
        commands_with_all_tags = self.all_commands.has_all_tags(
            ["Test Tag 1", "Test Tag 2"]
        )
        self.assertEqual(len(commands_with_all_tags), 1)
        self.assertIn(self.command_test_1, commands_with_all_tags)

        # Search all records in the model
        commands_with_all_tags = self.Command.has_all_tags(
            ["Test Tag 1", "Test Tag 2"], search_all=True
        )
        self.assertEqual(len(commands_with_all_tags), 1)
        self.assertIn(self.command_test_1, commands_with_all_tags)

        # Search with invalid type (should return empty recordset)
        commands_with_all_tags = self.Command.has_all_tags(123)
        self.assertEqual(len(commands_with_all_tags), 0)

        # Search with no tags (should return empty recordset)
        commands_with_all_tags = self.Command.has_all_tags([])
        self.assertEqual(len(commands_with_all_tags), 0)
