# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from ..hooks import XMLIDS_TO_BASE, _move_server_xmlids_to_base
from .common import TestTowerBaseCommon


class TestTowerBaseHooks(TestTowerBaseCommon):
    """Tests for the xmlid re-own helper used by pre_init_hook."""

    def test_move_listed_rows_keeps_res_id(self):
        """Listed xmlids move back to base and keep the same res_id."""
        cr = self.env.cr
        expected_res_ids = {}
        for name, model in XMLIDS_TO_BASE:
            cr.execute(
                """
                SELECT res_id
                  FROM ir_model_data
                 WHERE module = 'cetmix_tower_base'
                   AND name = %s
                   AND model = %s
                """,
                (name, model),
            )
            row = cr.fetchone()
            self.assertTrue(row, f"Missing xmlid cetmix_tower_base.{name}")
            expected_res_ids[name] = row[0]
            cr.execute(
                """
                UPDATE ir_model_data
                   SET module = 'cetmix_tower_server'
                 WHERE module = 'cetmix_tower_base'
                   AND name = %s
                   AND model = %s
                """,
                (name, model),
            )

        moved = _move_server_xmlids_to_base(cr)
        self.assertEqual(moved, len(XMLIDS_TO_BASE))
        self.assertEqual(_move_server_xmlids_to_base(cr), 0)
        self.env.registry.clear_cache()

        for name, model in XMLIDS_TO_BASE:
            xmlid = f"cetmix_tower_base.{name}"
            record = self.env.ref(xmlid)
            self.assertEqual(record.id, expected_res_ids[name])
            self.assertEqual(record._name, model)
            cr.execute(
                """
                SELECT id
                  FROM ir_model_data
                 WHERE module = 'cetmix_tower_server'
                   AND name = %s
                """,
                (name,),
            )
            self.assertFalse(cr.fetchone())

    def test_move_is_idempotent(self):
        """A second run after a real move updates zero rows and does not raise."""
        cr = self.env.cr
        for name, model in XMLIDS_TO_BASE:
            cr.execute(
                """
                UPDATE ir_model_data
                   SET module = 'cetmix_tower_server'
                 WHERE module = 'cetmix_tower_base'
                   AND name = %s
                   AND model = %s
                """,
                (name, model),
            )
        first = _move_server_xmlids_to_base(cr)
        self.assertEqual(first, len(XMLIDS_TO_BASE))
        second = _move_server_xmlids_to_base(cr)
        self.assertEqual(second, 0)

    def test_move_skips_collision(self):
        """Existing base xmlid blocks the server row; no IntegrityError."""
        name, model = XMLIDS_TO_BASE[0]
        cr = self.env.cr
        cr.execute(
            """
            SELECT res_id, noupdate
              FROM ir_model_data
             WHERE module = 'cetmix_tower_base'
               AND name = %s
            """,
            (name,),
        )
        base_res_id, base_noupdate = cr.fetchone()
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES ('cetmix_tower_server', %s, %s, %s, false)
            RETURNING id
            """,
            (name, model, base_res_id),
        )
        extra_id = cr.fetchone()[0]

        def _delete_extra_xmlid():
            cr.execute("DELETE FROM ir_model_data WHERE id = %s", (extra_id,))

        self.addCleanup(_delete_extra_xmlid)

        moved = _move_server_xmlids_to_base(cr)
        self.assertEqual(moved, 0)
        cr.execute(
            """
            SELECT module, res_id
              FROM ir_model_data
             WHERE id = %s
            """,
            (extra_id,),
        )
        module, res_id = cr.fetchone()
        self.assertEqual(module, "cetmix_tower_server")
        self.assertEqual(res_id, base_res_id)

        cr.execute(
            """
            SELECT res_id, noupdate
              FROM ir_model_data
             WHERE module = 'cetmix_tower_base'
               AND name = %s
            """,
            (name,),
        )
        still_res_id, still_noupdate = cr.fetchone()
        self.assertEqual(still_res_id, base_res_id)
        self.assertEqual(still_noupdate, base_noupdate)

    def test_unlisted_rows_untouched(self):
        """Xmlids not in XMLIDS_TO_BASE stay on cetmix_tower_server."""
        cr = self.env.cr
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES (
                'cetmix_tower_server',
                'unlisted_xmlid_for_hook_test',
                'ir.ui.menu',
                %s,
                false
            )
            RETURNING id
            """,
            (self.env.ref("cetmix_tower_base.menu_root").id,),
        )
        extra_id = cr.fetchone()[0]

        def _delete_extra_xmlid():
            cr.execute("DELETE FROM ir_model_data WHERE id = %s", (extra_id,))

        self.addCleanup(_delete_extra_xmlid)

        _move_server_xmlids_to_base(cr)
        cr.execute(
            """
            SELECT module
              FROM ir_model_data
             WHERE id = %s
            """,
            (extra_id,),
        )
        self.assertEqual(cr.fetchone()[0], "cetmix_tower_server")
