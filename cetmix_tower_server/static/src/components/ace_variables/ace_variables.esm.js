/** @odoo-module **/

import {AceField} from "@web/views/fields/ace/ace_field";
import {CodeEditorTower} from "./code_editor_tower.esm";
import {registry} from "@web/core/registry";
import {_t} from "@web/core/l10n/translation";

class AceCommandField extends AceField {}

AceCommandField.template = "cetmix_tower_server.AceCommandField";
AceCommandField.components = {
    CodeEditorTower,
};

registry.category("fields").add("ace_tower", {
    component: AceCommandField,
    displayName: _t("Ace Tower Editor"),
    supportedOptions: [
        {
            label: _t("Mode"),
            name: "mode",
            type: "string",
        },
    ],
    supportedTypes: ["text", "html", "char"],
    extractProps: ({options}) => ({
        mode: options.mode,
    }),
});

export {AceCommandField};
