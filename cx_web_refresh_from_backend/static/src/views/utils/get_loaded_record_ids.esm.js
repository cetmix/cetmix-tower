/** @odoo-module */

/**
 * Get IDs of records currently loaded in list-like root models.
 * Supports both plain and grouped datasets.
 *
 * @param {Object} root - View root model (list/kanban)
 * @returns {Array<Number>}
 */
export function getLoadedRecordIds(root) {
    if (root.isGrouped) {
        const recordIds = [];
        const collectIds = (groups) => {
            for (const group of groups) {
                if (group.list && group.list.records) {
                    recordIds.push(...group.list.records.map((record) => record.resId));
                }
                if (group.groups) {
                    collectIds(group.groups);
                }
            }
        };
        collectIds(root.groups);
        return recordIds;
    }
    return root.records.map((record) => record.resId);
}

/**
 * Whether any loaded record id is present in the notification id list.
 * Uses a Set for O(n + m) membership checks instead of O(n * m) with includes.
 *
 * @param {Number[]} loadedIds - IDs currently visible in the view
 * @param {Number[]} rec_ids - IDs from the bus payload
 * @returns {Boolean}
 */
export function hasAnyLoadedIdInRecIds(loadedIds, rec_ids) {
    const recIdSet = new Set(rec_ids);
    return loadedIds.some((id) => recIdSet.has(id));
}

/**
 * Whether a single record id is in the notification id list.
 * Uses a Set for O(m) build + O(1) lookup vs repeated includes.
 *
 * @param {Number|undefined|false} resId - Current record id (e.g. form root)
 * @param {Number[]} rec_ids - IDs from the bus payload
 * @returns {Boolean}
 */
export function isResIdInRecIds(resId, rec_ids) {
    if (!resId) {
        return false;
    }
    return new Set(rec_ids).has(resId);
}
