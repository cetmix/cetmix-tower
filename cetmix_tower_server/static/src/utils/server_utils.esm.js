/** @odoo-module */

/**
 * List of colors according to the selection value
 */
export const STATUS_COLORS = {
    false: "info",
    stopped: "danger",
    starting: "warning",
    running: "success",
    stopping: "warning",
    restarting: "warning",
    delete_error: "danger",
};

export const STATUS_COLOR_PREFIX =
    "o_server_status_bubble mx-0 o_color_server_status_bubble_";
