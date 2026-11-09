# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import TestTowerBaseCommon


class TestReferenceMixinBatch(TestTowerBaseCommon):
    """References of records created together in one batch"""

    def test_same_name_in_batch(self):
        """Records with the same name in one batch get unique references"""
        tags = self.Tag.create(
            [{"name": "Batch Tag"}, {"name": "Batch Tag"}, {"name": "Batch Tag"}]
        )
        self.assertEqual(
            tags.mapped("reference"), ["batch_tag", "batch_tag_2", "batch_tag_3"]
        )

    def test_same_reference_in_batch(self):
        """Explicit equal references in one batch are made unique"""
        tags = self.Tag.create(
            [
                {"name": "Batch Ref 1", "reference": "batch_ref"},
                {"name": "Batch Ref 2", "reference": "batch_ref"},
            ]
        )
        self.assertEqual(tags.mapped("reference"), ["batch_ref", "batch_ref_2"])

    def test_batch_and_database(self):
        """A batch reference is unique against the database too"""
        self.Tag.create({"name": "Existing Tag"})
        tags = self.Tag.create([{"name": "Existing Tag"}, {"name": "Existing Tag"}])
        self.assertEqual(tags.mapped("reference"), ["existing_tag_2", "existing_tag_3"])
