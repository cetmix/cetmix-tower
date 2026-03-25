/** @odoo-module */
/* global QUnit */

import "cx_web_refresh_from_backend/static/src/views/form/form_controller_patch.esm";
import "cx_web_refresh_from_backend/static/src/views/kanban/kanban_controller_patch.esm";
import "cx_web_refresh_from_backend/static/src/views/list/list_controller_patch.esm";

import {
    editInput,
    getFixture,
    makeDeferred,
    nextTick,
} from "@web/../tests/helpers/utils";
import {
    makeView,
    makeViewInDialog,
    setupViewRegistries,
} from "@web/../tests/views/helpers";

let serverData = null;
let target = null;

/**
 * Simulate a web.refresh_view notification on the patched controller.
 *
 * The unit tests exercise the controller filtering and refresh logic, so they
 * can call the public notification handler directly instead of reproducing the
 * bus service internals.
 *
 * @param {Object} controller - Patched view controller instance
 * @param {Object} payload - {model, view_types, rec_ids}
 * @returns {Promise<void>}
 */
function triggerRefresh(controller, payload) {
    return controller._onWebRefreshNotification(payload);
}

QUnit.module("cx_web_refresh_from_backend", (hooks) => {
    hooks.beforeEach(() => {
        serverData = {
            models: {
                "res.partner": {
                    fields: {
                        name: {string: "Name", type: "char"},
                    },
                    records: [
                        {id: 1, name: "Partner 1"},
                        {id: 2, name: "Partner 2"},
                    ],
                },
            },
        };
        setupViewRegistries();
        target = getFixture();
    });

    QUnit.test(
        "form: refresh runs only for matching notifications",
        async function (assert) {
            const form = await makeView({
                type: "form",
                resModel: "res.partner",
                serverData,
                resId: 1,
                arch: '<form><field name="name"/></form>',
            });

            let refreshCalls = 0;
            form.refreshForm = async () => {
                refreshCalls++;
            };

            triggerRefresh(form, {
                model: "res.users",
                view_types: ["form"],
                rec_ids: [1],
            });
            triggerRefresh(form, {
                model: "res.partner",
                view_types: ["list"],
                rec_ids: [1],
            });
            triggerRefresh(form, {
                model: "res.partner",
                view_types: ["form"],
                rec_ids: [2],
            });
            triggerRefresh(form, {
                model: "res.partner",
                view_types: ["form"],
                rec_ids: [1],
            });
            await nextTick();

            assert.strictEqual(refreshCalls, 1);
        }
    );

    QUnit.test(
        "form in dialog: matching notification is ignored",
        async function (assert) {
            const form = await makeViewInDialog({
                type: "form",
                resModel: "res.partner",
                serverData,
                resId: 1,
                arch: '<form><field name="name"/></form>',
            });

            let refreshCalls = 0;
            form.refreshForm = async () => {
                refreshCalls++;
            };

            triggerRefresh(form, {
                model: "res.partner",
                view_types: ["form"],
                rec_ids: [1],
            });
            await nextTick();

            assert.strictEqual(refreshCalls, 0);
        }
    );

    QUnit.test(
        "form: dirty form reloads from backend without confirmation dialog",
        async function (assert) {
            const form = await makeView({
                type: "form",
                resModel: "res.partner",
                serverData,
                resId: 1,
                arch: '<form><field name="name"/></form>',
            });

            await form.model.root.switchMode("edit");
            await editInput(
                target,
                ".o_field_widget[name='name'] input",
                "Changed Name"
            );

            triggerRefresh(form, {
                model: "res.partner",
                view_types: ["form"],
                rec_ids: [1],
            });
            await nextTick();
            await nextTick();

            assert.containsNone(
                target,
                ".modal",
                "backend refresh must not open a confirmation dialog"
            );
        }
    );

    QUnit.test("list: burst notifications are coalesced", async function (assert) {
        const list = await makeView({
            type: "list",
            resModel: "res.partner",
            serverData,
            arch: '<list><field name="name"/></list>',
        });

        const deferred = makeDeferred();
        let refreshCalls = 0;
        list.refreshList = async () => {
            refreshCalls++;
            if (refreshCalls === 1) {
                await deferred;
            }
        };

        const payload = {model: "res.partner", view_types: ["list"], rec_ids: [1]};
        triggerRefresh(list, payload);
        triggerRefresh(list, payload);
        triggerRefresh(list, payload);
        await nextTick();

        assert.strictEqual(
            refreshCalls,
            1,
            "only one refresh should run while in flight"
        );

        deferred.resolve();
        await nextTick();
        await nextTick();

        assert.strictEqual(
            refreshCalls,
            2,
            "one additional refresh should run after in-flight refresh finishes"
        );
    });

    QUnit.test("kanban: burst notifications are coalesced", async function (assert) {
        const kanban = await makeView({
            type: "kanban",
            resModel: "res.partner",
            serverData,
            arch: '<kanban><templates><t t-name="card"><div><field name="name"/></div></t></templates></kanban>',
        });

        const deferred = makeDeferred();
        let refreshCalls = 0;
        kanban.refreshList = async () => {
            refreshCalls++;
            if (refreshCalls === 1) {
                await deferred;
            }
        };

        const payload = {model: "res.partner", view_types: ["kanban"], rec_ids: [1]};
        triggerRefresh(kanban, payload);
        triggerRefresh(kanban, payload);
        triggerRefresh(kanban, payload);
        await nextTick();

        assert.strictEqual(
            refreshCalls,
            1,
            "only one refresh should run while in flight"
        );

        deferred.resolve();
        await nextTick();
        await nextTick();

        assert.strictEqual(
            refreshCalls,
            2,
            "one additional refresh should run after in-flight refresh finishes"
        );
    });
});
