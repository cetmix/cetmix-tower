# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.orm.model_classes import add_to_registry

from .common import TestTowerBaseCommon


class TestAccessRoleMixin(TestTowerBaseCommon):
    """Deferred child commands must not run alongside parent-create defaults."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        class RoleResource(models.Model):
            _name = "cx.tower.test.role.resource"
            _inherit = "cx.tower.access.role.mixin"
            _description = "Tower role test resource"

            name = fields.Char(default="Other default")
            user_ids = fields.Many2many(relation="tower_test_role_user_rel")
            manager_ids = fields.Many2many(relation="tower_test_role_manager_rel")
            child_ids = fields.One2many(
                "cx.tower.test.role.child",
                "resource_id",
                default=lambda self: [fields.Command.create({"name": "Field default"})],
            )

            def _get_post_create_fields(self):
                return ["child_ids"]

        class RoleChild(models.Model):
            _name = "cx.tower.test.role.child"
            _description = "Tower role test child"

            name = fields.Char()
            resource_id = fields.Many2one("cx.tower.test.role.resource")

        model_names = [RoleResource._name, RoleChild._name]
        for model in (RoleResource, RoleChild):
            add_to_registry(cls.registry, model)
            cls.addClassCleanup(cls.registry.__delitem__, model._name)
        cls.registry._setup_models__(cls.env.cr, model_names)
        cls.registry.init_models(cls.env.cr, model_names, {"models_to_check": True})
        cls.Resource = cls.env[RoleResource._name]

    def test_explicit_children_override_defaults(self):
        """Only explicit child commands execute; other defaults still apply."""
        for resource_model in (
            self.Resource,
            self.Resource.with_context(
                default_child_ids=[fields.Command.create({"name": "Context default"})]
            ),
        ):
            resource = resource_model.create(
                {"child_ids": [fields.Command.create({"name": "Explicit child"})]}
            )
            self.assertEqual(resource.child_ids.mapped("name"), ["Explicit child"])
            self.assertEqual(resource.name, "Other default")

    def test_missing_children_use_defaults(self):
        """Unspecified deferred fields keep their usual field/context defaults."""
        resource = self.Resource.create({})
        self.assertEqual(resource.child_ids.mapped("name"), ["Field default"])
        resource = self.Resource.with_context(
            default_child_ids=[fields.Command.create({"name": "Context default"})]
        ).create({})
        self.assertEqual(resource.child_ids.mapped("name"), ["Context default"])
