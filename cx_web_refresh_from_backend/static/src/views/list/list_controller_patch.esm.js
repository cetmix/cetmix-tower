/** @odoo-module */

import {
    getLoadedRecordIds,
    hasAnyLoadedIdInRecIds,
} from "../utils/get_loaded_record_ids.esm";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {ListController} from "@web/views/list/list_controller";
import {onWillUnmount} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

patch(ListController.prototype, {
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
     * Handle a web.refresh_view bus notification for this list.
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
     * Check whether a refresh notification is relevant to this list.
     *
     * Returns true when all of the following hold:
     *  - model matches current list model
     *  - requested view types include "list" or "tree" (or none specified)
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
        if (
            view_types.length > 0 &&
            !view_types.includes("list") &&
            !view_types.includes("tree")
        ) {
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
     * Refresh the list with actual data from server.
     * If there is an edited record, asks the user to save or cancel.
     *
     * @returns {Promise<void>}
     */
    async refreshList() {
        if (!this.model || !this.model.root) {
            return;
        }

        const list = this.model.root;

        if (list.editedRecord) {
            const confirmed = await this._confirmListRefresh();

            if (!confirmed) {
                // User declined: drop coalesced refreshes queued during the dialog.
                this._hasRefreshQueued = false;
                return;
            }
            try {
                await list.editedRecord.save();
            } catch (error) {
                this.notificationService.add(this._getSaveErrorMessage(error), {
                    type: "danger",
                });
                return;
            }
        }

        try {
            await list.load();
        } catch (error) {
            this.notificationService.add(this._getReloadErrorMessage(error), {
                type: "danger",
            });
            return;
        }

        if (this.model && this.model.root) {
            this.render(true);
        }
    },

    async _confirmListRefresh() {
        return await new Promise((resolve) => {
            this.dialogService.add(ConfirmationDialog, {
                title: _t("List is being refreshed from backend"),
                body: _t("You have unsaved edits. Save them before refreshing?"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
                confirmLabel: _t("Save & Refresh"),
                cancelLabel: _t("Cancel"),
            });
        });
    },

    _getSaveErrorMessage(error) {
        const message =
            (error && error.data && error.data.message) ||
            (error && error.message) ||
            String(error);
        return _t("Could not save record. %(message)s", {message});
    },

    _getReloadErrorMessage(error) {
        const message =
            (error && error.data && error.data.message) ||
            (error && error.message) ||
            String(error);
        return _t("Could not reload list. %(message)s", {message});
    },
});
