/** @odoo-module */

import {FormController} from "@web/views/form/form_controller";
import {isResIdInRecIds} from "../utils/get_loaded_record_ids.esm";
import {onWillUnmount} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        // Bus_service is async; useService("bus_service") breaks (SERVICES_METADATA).
        this.busService = this.env.services.bus_service;
        this.notificationService = useService("notification");

        this._lastLocalSave = null;
        this._isRefreshInFlight = false;
        this._hasRefreshQueued = false;

        this._boundBusHandler = this._onWebRefreshNotification.bind(this);
        this.busService.subscribe("web.refresh_view", this._boundBusHandler);

        onWillUnmount(() => {
            if (this.busService && this._boundBusHandler) {
                this.busService.unsubscribe("web.refresh_view", this._boundBusHandler);
            }
        });
    },

    /**
     * Handle a web.refresh_view bus notification for this form.
     * Called once per notification; coalesces concurrent refreshes via _queueRefresh.
     *
     * @param {Object} payload - Notification payload {model, view_types, rec_ids}
     */
    async _onWebRefreshNotification(payload) {
        if (!this.model || !this.model.root) {
            return;
        }
        if (this._shouldRefreshView(payload)) {
            await this._queueRefresh("refreshForm");
        }
    },

    async _queueRefresh(methodName) {
        if (this._isRefreshInFlight) {
            this._hasRefreshQueued = true;
            return;
        }
        this._isRefreshInFlight = true;
        try {
            do {
                this._hasRefreshQueued = false;
                await this[methodName]();
            } while (this._hasRefreshQueued);
        } finally {
            this._isRefreshInFlight = false;
        }
    },

    /**
     * Check whether a refresh notification is relevant to this form.
     *
     * Returns true when all of the following hold:
     *  - model matches current form model
     *  - requested view types include "form" (or none specified)
     *  - record id matches current record (or none specified)
     *  - form is not inside a dialog / wizard
     *
     * @param {Object} payload - Notification payload
     * @returns {Boolean}
     */
    _shouldRefreshView(payload) {
        const {model, view_types = [], rec_ids = []} = payload;

        if (this.props.resModel !== model) {
            return false;
        }
        if (view_types.length > 0 && !view_types.includes("form")) {
            return false;
        }
        const currentResId = this.model && this.model.root && this.model.root.resId;
        if (rec_ids.length > 0 && !isResIdInRecIds(currentResId, rec_ids)) {
            return false;
        }
        // Skip refresh when form is in a dialog or when a wizard is on top
        // of the stack. Refreshing in that context can leave wizard/confirmation
        // dialogs stuck open (e.g. confirm="..." in wizard view).
        if (this.env.inDialog) {
            return false;
        }
        const currentController = this.actionService.currentController;
        const currentAction = currentController && currentController.action;
        if (currentAction && currentAction.target === "new") {
            return false;
        }
        return true;
    },

    /**
     * Refresh the form with actual data from server.
     *
     * Reloads without confirmation even when the record is dirty (client changes
     * may be discarded). Dialog / wizard forms are filtered out in
     * _shouldRefreshView().
     *
     * @returns {Promise<void>}
     */
    async refreshForm() {
        if (this._lastLocalSave && Date.now() - this._lastLocalSave < 2500) {
            return;
        }

        if (!this.model || !this.model.root) {
            return;
        }

        const record = this.model.root;

        try {
            await record.load();
        } catch (error) {
            this.notificationService.add(this._getRefreshErrorMessage(error), {
                type: "danger",
            });
            return;
        }

        if (this.model && this.model.root) {
            this.render(true);
        }
    },

    _getRefreshErrorMessage(error) {
        const message =
            (error && error.data && error.data.message) ||
            (error && error.message) ||
            String(error);
        return _t("Could not reload form. %(message)s", {message});
    },

    /**
     * Override of save button handler.
     *
     * After a successful save, stores a timestamp to avoid immediate auto-refresh
     * triggered by our own write (bus notification). Failed saves leave the
     * timestamp unchanged so refresh suppression does not apply incorrectly.
     *
     * @param {Object} params - Save options
     * @returns {Promise<Boolean|undefined>} Result of the core save (truthy when save succeeded)
     */
    async saveButtonClicked(params) {
        const result = await super.saveButtonClicked(params);
        if (result) {
            this._lastLocalSave = Date.now();
        }
        return result;
    },
});
