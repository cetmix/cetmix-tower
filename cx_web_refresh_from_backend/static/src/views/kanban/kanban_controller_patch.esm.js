/** @odoo-module **/

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
        // Bus_service is async; useService("bus_service") is unsafe (SERVICES_METADATA
        // stores the async flag, not method names — see web/static/src/core/utils/hooks.js).
        this.busService = this.env.services.bus_service;
        this.notificationService = useService("notification");
        this._isRefreshInFlight = false;
        this._hasRefreshQueued = false;

        this._boundBusHandler = this._onBusNotification.bind(this);
        this.busService.addEventListener("notification", this._boundBusHandler);

        onWillUnmount(() => {
            if (this.busService && this._boundBusHandler) {
                this.busService.removeEventListener(
                    "notification",
                    this._boundBusHandler
                );
            }
        });
    },

    /**
     * Handle bus notification batch for view refresh.
     * Coalesces the batch: if any notification matches, refreshes once.
     *
     * @param {Event} event - Bus notification event
     */
    async _onBusNotification({detail: notifications}) {
        if (!this.model || !this.model.root) {
            return;
        }
        const shouldRefresh = notifications.some(
            ({type, payload}) =>
                type === "web.refresh_view" && this._shouldRefreshView(payload)
        );
        if (shouldRefresh) {
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
            const message =
                (error && error.data && error.data.message) ||
                (error && error.message) ||
                String(error);
            this.notificationService.add(_t("Could not reload kanban. ") + message, {
                type: "danger",
            });
            return;
        }

        if (this.model && this.model.root) {
            this.render(true);
        }
    },
});
