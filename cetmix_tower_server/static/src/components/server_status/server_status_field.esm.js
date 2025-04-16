/** @odoo-module */

import {registry} from "@web/core/registry";
import {
    StateSelectionField,
    stateSelectionField,
} from "@web/views/fields/state_selection/state_selection_field";

import {STATUS_COLORS, STATUS_COLOR_PREFIX} from "../../utils/server_utils.esm";

export class ServerStatusField extends StateSelectionField {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.colorPrefix = STATUS_COLOR_PREFIX;
        this.colors = STATUS_COLORS;
    }

    /**
     * @override
     */
    get options() {
        return [[false, "Undefined"], ...super.options];
    }
}

export const serverStatusField = {
    ...stateSelectionField,
    component: ServerStatusField,
};

registry.category("fields").add("server_status", serverStatusField);
