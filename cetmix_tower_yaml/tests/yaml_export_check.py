# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def assert_yaml_export_attributes(test, required_models):
    """Check ``yaml_export`` on every concrete model that inherits the mixin.

    Relational fields use ``explode``, ``include`` or ``reference``.
    Scalar fields use ``True``. A related field that only copied the
    attribute is ignored: ``_yaml_export_mode`` reads the field's own keys.

    Args:
        test (BaseCase): Running test case.
        required_models (list): Model names that must be installed and checked.
    """
    mixin_cls = type(test.env["cx.tower.yaml.mixin"])
    checked = set()
    for model_name, model_cls in test.env.registry.items():
        if model_cls._abstract or not issubclass(model_cls, mixin_cls):
            continue
        model = test.env[model_name]
        for field_name, field in model._fields.items():
            mode = model._yaml_export_mode(field)
            if mode is None:
                continue
            if field.type in ("many2one", "one2many", "many2many"):
                test.assertIn(
                    mode,
                    ("explode", "include", "reference"),
                    f"{model_name}.{field_name}",
                )
            else:
                test.assertIs(mode, True, f"{model_name}.{field_name}")
        checked.add(model_name)
    for model_name in required_models:
        test.assertIn(model_name, checked)
