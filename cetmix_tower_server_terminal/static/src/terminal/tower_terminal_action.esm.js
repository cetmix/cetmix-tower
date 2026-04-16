/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";

const actionRegistry = registry.category("actions");
const INPUT_FLUSH_DELAY = 12;
const RESIZE_FLUSH_DELAY = 80;
const WATCHDOG_INTERVAL = 15000; // Ms between state checks / pusher-restart pings
const XTERM_CSS_URL = "https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.css";
const XTERM_JS_URL = "https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.js";
const XTERM_FIT_ADDON_URL =
    "https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.js";

let xtermAssetsPromise = null;

function loadStylesheetOnce(url) {
    if (document.querySelector(`link[data-cetmix-terminal-lib="${url}"]`)) {
        return;
    }
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = url;
    link.dataset.cetmixTerminalLib = url;
    document.head.appendChild(link);
}

function loadScriptOnce(url) {
    return new Promise((resolve, reject) => {
        const existing = document.querySelector(
            `script[data-cetmix-terminal-lib="${url}"]`
        );
        if (existing) {
            if (existing.dataset.loaded === "1") {
                resolve();
                return;
            }
            existing.addEventListener("load", () => resolve(), {once: true});
            existing.addEventListener(
                "error",
                () => reject(new Error(_t("Failed to load terminal script."))),
                {once: true}
            );
            return;
        }

        const script = document.createElement("script");
        script.src = url;
        script.async = false;
        script.dataset.cetmixTerminalLib = url;
        script.addEventListener(
            "load",
            () => {
                script.dataset.loaded = "1";
                resolve();
            },
            {once: true}
        );
        script.addEventListener(
            "error",
            () => reject(new Error(_t("Failed to load terminal script."))),
            {once: true}
        );
        document.head.appendChild(script);
    });
}

async function ensureXtermAssetsLoaded() {
    const fitAddonLoaded = Boolean(window.FitAddon?.FitAddon || window.FitAddon);
    if (window.Terminal && fitAddonLoaded) {
        return;
    }
    if (!xtermAssetsPromise) {
        xtermAssetsPromise = (async () => {
            loadStylesheetOnce(XTERM_CSS_URL);
            await loadScriptOnce(XTERM_JS_URL);
            await loadScriptOnce(XTERM_FIT_ADDON_URL);
        })().catch((error) => {
            xtermAssetsPromise = null;
            throw error;
        });
    }
    await xtermAssetsPromise;
}

export class TowerTerminalAction extends Component {
    static template = "cetmix_tower_server_terminal.TowerTerminalAction";
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this.outputRef = useRef("output");
        this.sessionId = this.props.action.params.session_id;

        this.term = null;
        this.fitAddon = null;
        this.resizeObserver = null;
        this.handleWindowResize = this.fitTerminal.bind(this);

        this.sendInFlight = false;
        this.resizeInFlight = false;
        this.watchdogHandle = null;
        this.inputBuffer = "";
        this.inputFlushHandle = null;
        this.resizeFlushHandle = null;
        this.queuedPayload = "";
        this.pendingTerminalSize = null;
        this.lastTerminalSize = {cols: 0, rows: 0};

        // Bus channel: matches the server-side f"terminal_{session_id}"
        this._busChannel = `terminal_${this.sessionId}`;
        this._busNotificationHandler = this._handleBusNotification.bind(this);

        this.state = useState({
            isSending: false,
            message: "",
            status: "connecting",
            title: this.props.action.params.title || _t("Server Terminal"),
        });

        this.env.config.setDisplayName(this.state.title);

        onWillStart(async () => {
            await ensureXtermAssetsLoaded();
        });

        onMounted(() => {
            this.initializeTerminal();
            this._subscribeBus();
            this.loadOutput();
            this.focusTerminal();
        });

        onWillUnmount(() => {
            this.clearInputFlushTimer();
            this.clearResizeFlushTimer();
            this.stopWatchdog();
            this._unsubscribeBus();
            this.unregisterResizeHandlers();
            this.disposeTerminal();
            this.closeTerminal(true);
        });
    }

    get statusClass() {
        if (this.state.status === "open") {
            return "text-bg-success";
        }
        if (this.state.status === "error") {
            return "text-bg-danger";
        }
        return "text-bg-secondary";
    }

    get statusLabel() {
        if (this.state.status === "open") {
            return _t("Connected");
        }
        if (this.state.status === "error") {
            return _t("Error");
        }
        if (this.state.status === "closed") {
            return _t("Disconnected");
        }
        return _t("Connecting");
    }

    get isConnected() {
        return this.state.status === "open";
    }

    async callSession(method, ...args) {
        return this.orm.call("cx.tower.terminal.session", method, [
            [this.sessionId],
            ...args,
        ]);
    }

    initializeTerminal() {
        const TerminalCtor = window.Terminal;
        if (!TerminalCtor) {
            this.handleError(
                new Error(_t("xterm.js failed to load.")),
                _t("Terminal UI failed to initialize.")
            );
            return;
        }

        const FitAddonCtor = window.FitAddon?.FitAddon || window.FitAddon;
        this.term = new TerminalCtor({
            cursorBlink: true,
            fontFamily: "IBM Plex Mono, Fira Code, monospace",
            fontSize: 14,
            lineHeight: 1.25,
            scrollback: 6000,
            theme: {
                background: "#000000",
                foreground: "#f8fafc",
                cursor: "#86efac",
                cursorAccent: "#000000",
            },
        });

        if (FitAddonCtor) {
            this.fitAddon = new FitAddonCtor();
            this.term.loadAddon(this.fitAddon);
        }

        this.term.onData((data) => this.handleTerminalInput(data));
        this.term.open(this.outputRef.el);
        this.registerResizeHandlers();
        this.fitTerminal();
    }

    registerResizeHandlers() {
        window.addEventListener("resize", this.handleWindowResize);
        if (window.ResizeObserver && this.outputRef.el) {
            this.resizeObserver = new ResizeObserver(() => this.fitTerminal());
            this.resizeObserver.observe(this.outputRef.el);
        }
    }

    unregisterResizeHandlers() {
        window.removeEventListener("resize", this.handleWindowResize);
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
    }

    disposeTerminal() {
        if (this.term) {
            this.term.dispose();
            this.term = null;
        }
        this.fitAddon = null;
    }

    fitTerminal() {
        if (this.fitAddon && this.term) {
            this.fitAddon.fit();
            this.scheduleResizeSync();
        }
    }

    _subscribeBus() {
        this.busService.addChannel(this._busChannel);
        this.busService.subscribe("terminal.output", this._busNotificationHandler);
    }

    _unsubscribeBus() {
        this.busService.unsubscribe("terminal.output", this._busNotificationHandler);
        this.busService.deleteChannel(this._busChannel);
    }

    _handleBusNotification(payload) {
        // Filter to our session (defensive; channel already scopes it)
        if (String(payload.session_id) !== String(this.sessionId)) {
            return;
        }
        this.writeOutput(payload.output);
        if (payload.state && payload.state !== this.state.status) {
            this.state.status = payload.state;
        }
        if (payload.message) {
            this.state.message = payload.message;
        }
        if (!this.isConnected) {
            this.stopWatchdog();
        }
    }

    startWatchdog() {
        if (this.watchdogHandle || !this.isConnected) {
            return;
        }
        this.watchdogHandle = window.setInterval(async () => {
            if (!this.isConnected) {
                this.stopWatchdog();
                return;
            }
            // Ping server: checks session state and restarts pusher if dead
            await this.loadOutput({silent: true});
        }, WATCHDOG_INTERVAL);
    }

    stopWatchdog() {
        if (this.watchdogHandle) {
            window.clearInterval(this.watchdogHandle);
            this.watchdogHandle = null;
        }
    }

    writeOutput(output) {
        if (!output || !this.term) {
            return;
        }
        this.term.write(output);
        this.scrollToBottom();
    }

    applyResponse(response) {
        if (!response) {
            return;
        }
        this.state.status = response.state || this.state.status;
        this.state.message = response.message || "";
        // Fallback: write output that came with the RPC response directly
        // (initial shell banner, or if bus delivery is unavailable)
        this.writeOutput(response.output);
        if (this.isConnected) {
            this.startWatchdog();
            this.scheduleResizeSync();
        } else {
            this.stopWatchdog();
        }
    }

    async loadOutput({silent = false} = {}) {
        try {
            const response = await this.callSession("terminal_read");
            this.applyResponse(response);
        } catch (error) {
            if (!silent) {
                this.handleError(error, _t("Failed to open terminal output."));
            }
        }
    }

    handleTerminalInput(data) {
        if (!data || !this.isConnected) {
            return;
        }
        this.inputBuffer += data;
        if (this.shouldFlushInputImmediately(data)) {
            this.flushInputBuffer();
            return;
        }
        this.scheduleInputFlush();
    }

    shouldFlushInputImmediately(data) {
        return /[\r\n\t\u0003\u0004\u001b]/.test(data);
    }

    scheduleInputFlush() {
        if (this.inputFlushHandle) {
            return;
        }
        this.inputFlushHandle = window.setTimeout(() => {
            this.inputFlushHandle = null;
            this.flushInputBuffer();
        }, INPUT_FLUSH_DELAY);
    }

    clearInputFlushTimer() {
        if (this.inputFlushHandle) {
            window.clearTimeout(this.inputFlushHandle);
            this.inputFlushHandle = null;
        }
    }

    flushInputBuffer() {
        if (!this.inputBuffer) {
            this.clearInputFlushTimer();
            return;
        }
        const payload = this.inputBuffer;
        this.inputBuffer = "";
        this.clearInputFlushTimer();
        this.queuePayload(payload);
    }

    queuePayload(payload) {
        if (!payload || !this.isConnected) {
            return;
        }

        this.queuedPayload += payload;
        this.state.isSending = true;
        this.processSendQueue();
    }

    async processSendQueue() {
        if (this.sendInFlight || !this.isConnected) {
            return;
        }

        this.sendInFlight = true;
        try {
            while (this.isConnected && this.queuedPayload) {
                const payload = this.queuedPayload;
                this.queuedPayload = "";
                try {
                    const response = await this.callSession("terminal_send", payload);
                    this.applyResponse(response);
                } catch (error) {
                    this.handleError(error, _t("Failed to send data to terminal."));
                    this.queuedPayload = `${payload}${this.queuedPayload}`;
                    return;
                }
            }
        } finally {
            this.sendInFlight = false;
            this.state.isSending = Boolean(this.queuedPayload);
            this.focusTerminal();
            if (this.queuedPayload && this.isConnected) {
                this.processSendQueue();
            }
        }
    }

    scheduleResizeSync() {
        if (!this.term || !this.isConnected) {
            return;
        }
        if (this.resizeFlushHandle) {
            return;
        }
        this.resizeFlushHandle = window.setTimeout(() => {
            this.resizeFlushHandle = null;
            this.flushResizeSync();
        }, RESIZE_FLUSH_DELAY);
    }

    clearResizeFlushTimer() {
        if (this.resizeFlushHandle) {
            window.clearTimeout(this.resizeFlushHandle);
            this.resizeFlushHandle = null;
        }
    }

    flushResizeSync() {
        if (!this.term || !this.isConnected) {
            return;
        }
        const cols = this.term.cols;
        const rows = this.term.rows;
        if (!cols || !rows) {
            return;
        }
        if (
            cols === this.lastTerminalSize.cols &&
            rows === this.lastTerminalSize.rows &&
            !this.pendingTerminalSize
        ) {
            return;
        }
        this.pendingTerminalSize = {cols, rows};
        this.processResizeQueue();
    }

    async processResizeQueue() {
        if (this.resizeInFlight || !this.isConnected || !this.pendingTerminalSize) {
            return;
        }

        const size = this.pendingTerminalSize;
        let shouldRetryLater = false;
        this.pendingTerminalSize = null;
        if (
            size.cols === this.lastTerminalSize.cols &&
            size.rows === this.lastTerminalSize.rows
        ) {
            return;
        }

        this.resizeInFlight = true;
        try {
            const response = await this.callSession(
                "terminal_resize",
                size.cols,
                size.rows
            );
            this.lastTerminalSize = size;
            this.applyResponse(response);
        } catch {
            this.pendingTerminalSize = size;
            shouldRetryLater = true;
        } finally {
            this.resizeInFlight = false;
            if (this.pendingTerminalSize && this.isConnected) {
                if (shouldRetryLater) {
                    this.scheduleResizeSync();
                } else {
                    this.processResizeQueue();
                }
            }
        }
    }

    async closeTerminal(silent = false) {
        try {
            const response = await this.callSession("terminal_close");
            if (!silent) {
                this.applyResponse(response);
            }
        } catch (error) {
            if (!silent) {
                this.handleError(error, _t("Failed to close terminal session."));
            }
        } finally {
            this.state.status = "closed";
            this.stopWatchdog();
        }
    }

    async reconnectTerminal() {
        this.state.isSending = true;
        try {
            this.clearInputFlushTimer();
            this.clearResizeFlushTimer();
            this.inputBuffer = "";
            this.queuedPayload = "";
            this.pendingTerminalSize = null;
            this.sendInFlight = false;
            this.resizeInFlight = false;
            this.lastTerminalSize = {cols: 0, rows: 0};
            if (this.term) {
                this.term.reset();
            }
            const response = await this.callSession("terminal_reconnect");
            this.applyResponse(response);
        } catch (error) {
            this.handleError(error, _t("Failed to reconnect terminal session."));
        } finally {
            this.state.isSending = false;
            this.focusTerminal();
        }
    }

    clearOutput() {
        if (this.term) {
            this.term.reset();
        }
        this.focusTerminal();
    }

    focusTerminal() {
        if (this.term) {
            this.term.focus();
        }
    }

    scrollToBottom() {
        if (this.term) {
            this.term.scrollToBottom();
        }
    }

    handleError(error, fallbackMessage) {
        const message = error?.message || error?.data?.message || fallbackMessage;
        this.state.status = "error";
        this.state.message = message;
        this.stopWatchdog();
        this.notification.add(message, {type: "danger"});
    }
}

actionRegistry.add("cetmix_tower_server_terminal.terminal", TowerTerminalAction);
