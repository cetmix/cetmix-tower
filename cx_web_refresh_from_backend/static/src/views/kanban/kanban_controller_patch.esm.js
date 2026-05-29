/** @odoo-module */

import {
    getLoadedRecordIds,
    hasAnyLoadedIdInRecIds,
} from "../utils/get_loaded_record_ids.esm";
import {KanbanController} from "@web/views/kanban/kanban_controller";
import {onWillUnmount} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        // Bus_service is async; useService("bus_service") breaks (SERVICES_METADATA).
        this.busService = this.env.services.bus_service;
        this.notificationService = useService("notification");
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
     * Handle a web.refresh_view bus notification for this kanban.
     * Called once per notification; coalesces concurrent refreshes via _queueRefresh.
     *
     * @param {Object} payload - Notification payload {model, view_types, rec_ids}
     */
    async _onWebRefreshNotification(payload) {
        if (!this.model || !this.model.root) {
            return;
        }
        if (this._shouldRefreshView(payload)) {
            await this._queueRefresh("refreshList");
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
     * Check whether a refresh notification is relevant to this kanban.
     *
     * Returns true when all of the following hold:
     *  - model matches current kanban model
     *  - requested view types include "kanban" (or none specified)
     *  - at least one loaded record id is in rec_ids (or none specified)
     *
     * @param {Object} payload - Notification payload
     * @returns {Boolean}
     */
    _shouldRefreshView(payload) {
        const {model, view_types = [], rec_ids = []} = payload;

        if (this.props.resModel !== model) {
            return false;
        }
        if (view_types.length > 0 && !view_types.includes("kanban")) {
            return false;
        }
        if (rec_ids.length > 0) {
            const loadedIds = getLoadedRecordIds(this.model.root);
            if (!hasAnyLoadedIdInRecIds(loadedIds, rec_ids)) {
                return false;
            }
        }
        return true;
    },

    /**
     * Refresh the kanban with actual data from server.
     *
     * @returns {Promise<void>}
     */
    async refreshList() {
        if (!this.model || !this.model.root) {
            return;
        }

        const list = this.model.root;

        try {
            await list.load();
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
        return _t("Could not reload kanban. %(message)s", {message});
    },
});
