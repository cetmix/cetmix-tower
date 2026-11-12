/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useEffect,
    useRef,
    useState,
} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {loadBundle} from "@web/core/assets";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";

const XTERM_BUNDLE = "cetmix_tower_server_terminal.assets_xterm";
const NOTIFICATION_TYPE = "cx_tower_terminal.output";

// Milliseconds the keys typed in the same instant are grouped for, so that
// typing fast does not send one request per character.
const INPUT_FLUSH_DELAY = 10;
// Milliseconds a resize waits, so that dragging a window sends one size.
const RESIZE_FLUSH_DELAY = 150;
// Characters sent in one call. The session refuses more, and a paste is
// easily larger than that.
const MAX_INPUT_CHUNK = 2000;
// Milliseconds the search waits for the typing to stop before it runs
const SEARCH_DELAY = 120;
// Milliseconds without any message from the session before it is given up on.
// The session sends a heartbeat every 20 seconds while it is alive, so silence
// means the process that owned it is gone.
const SESSION_TIMEOUT = 60000;

export class TowerTerminalAction extends Component {
    static template = "cetmix_tower_server_terminal.TowerTerminalAction";
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this.outputRef = useRef("output");
        this.searchInputRef = useRef("searchInput");

        this.sessionId = this.props.action.params.session_id;
        this.busChannel = this.props.action.params.bus_channel;

        this.term = null;
        this.fitAddon = null;
        this.resizeObserver = null;
        this.onWindowResize = this.fitTerminal.bind(this);
        this.onNotification = this.handleNotification.bind(this);
        // The bus runs in a worker shared by every tab, which outlives this
        // page: a channel that is not deleted before the page goes away keeps
        // being subscribed to by the next one. A page the browser only puts in
        // its back forward cache is not gone, and comes back without mounting
        // again, so it keeps its subscription.
        this.onPageHide = (event) => {
            if (!event.persisted) {
                this.unsubscribe();
            }
        };
        this.onPageShow = (event) => {
            if (event.persisted) {
                this.subscribe();
                this.watchSession();
            }
        };

        this.inputBuffer = "";
        this.pendingInput = "";
        this.inputInFlight = false;
        this.inputTimer = null;
        this.resizeTimer = null;
        this.sessionTimer = null;
        this.lastSize = {cols: 0, rows: 0};
        this.sizeHintTimer = null;
        this.bellTimer = null;
        this.searchTimer = null;
        this.searchAddon = null;
        this.onFocusIn = () => (this.state.isFocused = true);
        this.onFocusOut = () => (this.state.isFocused = false);

        this.state = useState({
            status: "connecting",
            message: "",
            title: this.props.action.params.title || _t("Server Terminal"),
            serverName: this.props.action.params.server_name || "",
            target: this.props.action.params.target || "",
            // Size of the terminal, shown for a moment after it changes
            sizeHint: "",
            isFocused: false,
            isBusy: false,
            // The overlay hides the screen while the session is not usable. It
            // can be put away to read or copy what the session left behind.
            overlayDismissed: false,
            isFullScreen: false,
            // Output arrived while the user was reading further up
            hasUnreadOutput: false,
            isBelling: false,
            search: {open: false, term: "", current: 0, total: 0},
        });
        this.env.config.setDisplayName(this.state.title);

        onWillStart(() => loadBundle(XTERM_BUNDLE));

        // The input only exists once the panel is rendered, so the focus has to
        // wait for the patch instead of for the next microtask.
        useEffect(
            (isOpen) => {
                if (isOpen) {
                    this.searchInputRef.el?.focus();
                }
            },
            () => [this.state.search.open]
        );

        onMounted(() => {
            this.initializeTerminal();
            this.subscribe();
            this.watchSession();
            this.outputRef.el.addEventListener("focusin", this.onFocusIn);
            this.outputRef.el.addEventListener("focusout", this.onFocusOut);
            window.addEventListener("pagehide", this.onPageHide);
            window.addEventListener("pageshow", this.onPageShow);
        });

        onWillUnmount(() => {
            this.clearTimers();
            this.outputRef.el.removeEventListener("focusin", this.onFocusIn);
            this.outputRef.el.removeEventListener("focusout", this.onFocusOut);
            window.removeEventListener("pagehide", this.onPageHide);
            window.removeEventListener("pageshow", this.onPageShow);
            this.unsubscribe();
            this.unregisterResizeHandlers();
            // Courtesy call so the shell goes away at once. The server does not
            // depend on it: it also closes the session when the websocket of
            // this browser goes away, and when the session sits idle.
            this.callSession("terminal_close").catch(() => {
                // Nothing to do, the server closes the session on its own.
            });
            this.disposeTerminal();
        });
    }

    // -- Status shown in the toolbar

    get isConnected() {
        return this.state.status === "open";
    }

    get showOverlay() {
        return this.state.status !== "open" && !this.state.overlayDismissed;
    }

    get overlayIcon() {
        if (this.state.status === "connecting") {
            return "fa-spinner fa-spin";
        }
        if (this.state.status === "error") {
            return "fa-exclamation-triangle";
        }
        return "fa-plug";
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

    // -- Terminal

    initializeTerminal() {
        this.term = new window.Terminal({
            // Needed by the search addon to highlight what it finds. It is the
            // opt in xterm asks for to use an api it may still change.
            allowProposedApi: true,
            cursorBlink: true,
            fontFamily: "IBM Plex Mono, Fira Code, monospace",
            fontSize: 14,
            lineHeight: 1.25,
            scrollback: 6000,
            theme: {
                background: "#0a0e17",
                foreground: "#e2e8f0",
                cursor: "#60a5fa",
                cursorAccent: "#0a0e17",
                selectionBackground: "rgba(96, 165, 250, 0.3)",
            },
        });
        this.fitAddon = new window.FitAddon.FitAddon();
        this.term.loadAddon(this.fitAddon);
        this.searchAddon = new window.SearchAddon.SearchAddon();
        this.term.loadAddon(this.searchAddon);
        this.searchAddon.onDidChangeResults((results) => {
            this.state.search.current = results ? results.resultIndex + 1 : 0;
            this.state.search.total = results ? results.resultCount : 0;
        });
        this.term.onData((data) => this.queueInput(data));
        // A bell is the shell asking for attention: show it instead of ringing.
        this.term.onBell(() => this.flashBell());
        // Reading further up is not interrupted, so the terminal has to say
        // when it stopped following the output.
        this.term.onScroll(() => {
            if (this.isScrolledToBottom()) {
                this.state.hasUnreadOutput = false;
            }
        });
        this.term.attachCustomKeyEventHandler((event) => this.handleKey(event));
        this.term.open(this.outputRef.el);
        this.registerResizeHandlers();
        this.fitTerminal();
        this.term.focus();
        // The focus happens before the listeners below are in place.
        this.state.isFocused = true;
    }

    disposeTerminal() {
        if (this.term) {
            this.term.dispose();
            this.term = null;
        }
        this.fitAddon = null;
        this.searchAddon = null;
    }

    /**
     * Tell whether the viewport is following the output.
     *
     * @returns {Boolean}
     */
    isScrolledToBottom() {
        if (!this.term) {
            return true;
        }
        const buffer = this.term.buffer.active;
        return buffer.viewportY >= buffer.baseY;
    }

    scrollToBottom() {
        if (this.term) {
            this.term.scrollToBottom();
            this.state.hasUnreadOutput = false;
            this.term.focus();
        }
    }

    /**
     * Show the bell the shell rang. Terminals that beep in an office are a
     * nuisance, a short flash says the same thing.
     */
    flashBell() {
        this.state.isBelling = true;
        if (this.bellTimer) {
            window.clearTimeout(this.bellTimer);
        }
        this.bellTimer = window.setTimeout(() => {
            this.bellTimer = null;
            this.state.isBelling = false;
        }, 180);
    }

    /**
     * Handle the shortcuts the terminal takes for itself. Everything else is
     * left alone: the shell is the one that owns the keyboard.
     *
     * @param {KeyboardEvent} event
     * @returns {Boolean} False to keep the key from reaching the shell.
     */
    handleKey(event) {
        if (event.type !== "keydown") {
            return true;
        }
        const control = event.ctrlKey || event.metaKey;
        if (control && event.shiftKey && event.code === "KeyF") {
            this.openSearch();
            return false;
        }
        if (control && event.shiftKey && event.code === "KeyC") {
            this.copySelection();
            return false;
        }
        if (control && event.shiftKey && event.code === "KeyV") {
            this.pasteFromClipboard();
            return false;
        }
        return true;
    }

    async copySelection() {
        const selection = this.term?.getSelection();
        if (!selection) {
            return;
        }
        try {
            await navigator.clipboard.writeText(selection);
            this.notification.add(_t("Copied to the clipboard."), {type: "info"});
        } catch {
            // Clipboard access can be refused by the browser; the selection is
            // still there to be copied by hand.
            this.notification.add(_t("The browser refused access to the clipboard."), {
                type: "warning",
            });
        }
    }

    async pasteFromClipboard() {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                this.queueInput(text);
            }
        } catch {
            this.notification.add(_t("The browser refused access to the clipboard."), {
                type: "warning",
            });
        }
    }

    // -- Search

    openSearch() {
        this.state.search.open = true;
    }

    closeSearch() {
        this.state.search.open = false;
        this.state.search.term = "";
        this.state.search.current = 0;
        this.state.search.total = 0;
        this.searchAddon?.clearDecorations();
        // The addon selects the match it is on, which outlives the panel.
        this.term?.clearSelection();
        this.term?.focus();
    }

    onSearchInput(event) {
        this.state.search.term = event.target.value;
        // Every keystroke would walk the whole scrollback, so wait for a pause.
        if (this.searchTimer) {
            window.clearTimeout(this.searchTimer);
        }
        this.searchTimer = window.setTimeout(() => {
            this.searchTimer = null;
            this.findInScrollback();
        }, SEARCH_DELAY);
    }

    onSearchKeydown(event) {
        if (event.key === "Escape") {
            this.closeSearch();
        } else if (event.key === "Enter") {
            this.findInScrollback(event.shiftKey);
        }
    }

    /**
     * Look for the current term in the scrollback.
     *
     * @param {Boolean} backwards
     */
    findInScrollback(backwards = false) {
        if (!this.searchAddon) {
            return;
        }
        const term = this.state.search.term;
        if (!term) {
            this.searchAddon.clearDecorations();
            this.state.search.current = 0;
            this.state.search.total = 0;
            return;
        }
        const options = {
            decorations: {
                matchBackground: "#1e3a8a",
                matchBorder: "#60a5fa",
                matchOverviewRuler: "#60a5fa",
                activeMatchBackground: "#2563eb",
                activeMatchBorder: "#bfdbfe",
                activeMatchColorOverviewRuler: "#bfdbfe",
            },
        };
        try {
            if (backwards) {
                this.searchAddon.findPrevious(term, options);
            } else {
                this.searchAddon.findNext(term, options);
            }
        } catch (error) {
            // Searching is a convenience: it must never take the session down.
            this.state.search.total = 0;
            console.debug("[tower terminal] search failed:", error);
        }
    }

    // -- Full screen

    toggleFullScreen() {
        this.state.isFullScreen = !this.state.isFullScreen;
        // The box the terminal measures itself against just changed.
        Promise.resolve().then(() => this.fitTerminal());
    }

    registerResizeHandlers() {
        window.addEventListener("resize", this.onWindowResize);
        if (window.ResizeObserver && this.outputRef.el) {
            this.resizeObserver = new ResizeObserver(() => this.fitTerminal());
            this.resizeObserver.observe(this.outputRef.el);
        }
    }

    unregisterResizeHandlers() {
        window.removeEventListener("resize", this.onWindowResize);
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
    }

    fitTerminal() {
        if (!this.term || !this.fitAddon) {
            return;
        }
        this.fitAddon.fit();
        if (this.resizeTimer) {
            return;
        }
        this.resizeTimer = window.setTimeout(() => {
            this.resizeTimer = null;
            this.sendSize();
        }, RESIZE_FLUSH_DELAY);
    }

    // -- Output

    subscribe() {
        this.busService.addChannel(this.busChannel);
        this.busService.subscribe(NOTIFICATION_TYPE, this.onNotification);
    }

    unsubscribe() {
        this.busService.unsubscribe(NOTIFICATION_TYPE, this.onNotification);
        this.busService.deleteChannel(this.busChannel);
    }

    handleNotification(payload) {
        if (payload.session_id !== this.sessionId) {
            return;
        }
        this.watchSession();
        if (payload.output && this.term) {
            // Writing scrolls the viewport only when the user was already at
            // the bottom: a page being read must not jump under them.
            const wasAtBottom = this.isScrolledToBottom();
            this.term.write(payload.output, () => {
                if (wasAtBottom) {
                    this.term.scrollToBottom();
                } else {
                    this.state.hasUnreadOutput = true;
                }
            });
        }
        this.state.message = payload.message || "";
        if (payload.state === this.state.status) {
            return;
        }
        this.state.status = payload.state;
        if (this.isConnected) {
            this.state.overlayDismissed = false;
            // The shell is up: tell it how big the window actually is.
            this.sendSize(true);
        } else {
            this.clearTimers();
        }
    }

    /**
     * Give up on the session when it stops sending anything, heartbeats
     * included: the process that owned the shell is then gone for good.
     */
    watchSession() {
        if (this.sessionTimer) {
            window.clearTimeout(this.sessionTimer);
        }
        this.sessionTimer = window.setTimeout(() => {
            this.sessionTimer = null;
            if (this.isConnected || this.state.status === "connecting") {
                this.state.status = "closed";
                this.state.message = _t("Terminal session is no longer available.");
            }
        }, SESSION_TIMEOUT);
    }

    // -- Input

    queueInput(data) {
        if (!data || !this.isConnected) {
            return;
        }
        this.inputBuffer += data;
        if (this.inputTimer) {
            return;
        }
        this.inputTimer = window.setTimeout(() => {
            this.inputTimer = null;
            this.flushInput();
        }, INPUT_FLUSH_DELAY);
    }

    flushInput() {
        const payload = this.inputBuffer;
        this.inputBuffer = "";
        if (!payload || !this.isConnected) {
            return;
        }
        this.pendingInput += payload;
        this.drainInput();
    }

    /**
     * Send what is pending, one request at a time.
     *
     * Order matters — a command and the Enter that runs it cannot swap — but
     * waiting for each round trip before sending the next key makes the delay
     * grow with every letter: over a link of 287 ms, a six letter word took
     * 2.8 s to appear. Keys typed while a request is in flight are collected
     * and leave together with the next one, so the delay stays at one round
     * trip no matter how fast somebody types.
     */
    async drainInput() {
        if (this.inputInFlight || !this.pendingInput || !this.isConnected) {
            return;
        }
        const sessionId = this.sessionId;
        this.inputInFlight = true;
        try {
            while (this.pendingInput && this.isConnected) {
                const piece = this.pendingInput.slice(0, MAX_INPUT_CHUNK);
                this.pendingInput = this.pendingInput.slice(piece.length);
                await this.callSessionOn(sessionId, "terminal_send", piece);
            }
        } catch (error) {
            this.reportError(error, _t("Cannot reach the terminal."));
        } finally {
            this.inputInFlight = false;
        }
    }

    sendSize(force = false) {
        if (!this.term || !this.isConnected) {
            return;
        }
        const {cols, rows} = this.term;
        if (!cols || !rows) {
            return;
        }
        if (!force && cols === this.lastSize.cols && rows === this.lastSize.rows) {
            return;
        }
        this.lastSize = {cols, rows};
        this.showSizeHint(cols, rows);
        // Not queued behind the input: a size that arrives a moment early or
        // late is harmless, and the input must not wait for it.
        this.callSessionOn(this.sessionId, "terminal_resize", cols, rows).catch(
            (error) => this.reportError(error, _t("Cannot resize the terminal."))
        );
    }

    /**
     * Show the size of the terminal for a moment, the way a window manager
     * does, so a resize is not a silent change under a running program.
     *
     * @param {Number} cols
     * @param {Number} rows
     */
    showSizeHint(cols, rows) {
        this.state.sizeHint = `${cols} × ${rows}`;
        if (this.sizeHintTimer) {
            window.clearTimeout(this.sizeHintTimer);
        }
        this.sizeHintTimer = window.setTimeout(() => {
            this.sizeHintTimer = null;
            this.state.sizeHint = "";
        }, 1500);
    }

    // -- Actions of the toolbar

    clearOutput() {
        if (this.term) {
            this.term.reset();
            this.term.focus();
        }
    }

    async closeTerminal() {
        try {
            await this.callSession("terminal_close");
            this.state.status = "closed";
            this.state.message = _t("The session was closed from the browser.");
            this.clearTimers();
        } catch (error) {
            this.reportError(error, _t("Cannot close the terminal session."));
        }
    }

    dismissOverlay() {
        this.state.overlayDismissed = true;
    }

    async reconnectTerminal() {
        this.state.isBusy = true;
        try {
            const params = await this.callSession("terminal_reconnect");
            this.unsubscribe();
            this.sessionId = params.session_id;
            this.busChannel = params.bus_channel;
            this.lastSize = {cols: 0, rows: 0};
            this.inputBuffer = "";
            this.pendingInput = "";
            this.state.status = "connecting";
            this.state.message = "";
            this.state.overlayDismissed = false;
            if (this.term) {
                this.term.reset();
                this.term.focus();
            }
            this.subscribe();
            this.watchSession();
        } catch (error) {
            this.reportError(error, _t("Cannot reconnect the terminal session."));
        } finally {
            this.state.isBusy = false;
        }
    }

    // -- Helpers

    callSession(method, ...args) {
        return this.callSessionOn(this.sessionId, method, ...args);
    }

    /**
     * Call a method of one session, named when the call was queued.
     *
     * Input is chained, so a call can still be waiting when Reconnect replaces
     * the session. What was typed for a shell that is gone must not run in the
     * one that took its place.
     *
     * @param {Number} sessionId
     * @param {String} method
     * @param {...any} args
     * @returns {Promise<any>}
     */
    callSessionOn(sessionId, method, ...args) {
        if (sessionId !== this.sessionId) {
            return Promise.resolve(false);
        }
        return this.orm.call("cx.tower.terminal.session", method, [
            [sessionId],
            ...args,
        ]);
    }

    clearTimers() {
        const timers = [
            this.inputTimer,
            this.resizeTimer,
            this.sessionTimer,
            this.sizeHintTimer,
            this.bellTimer,
            this.searchTimer,
        ];
        for (const timer of timers) {
            if (timer) {
                window.clearTimeout(timer);
            }
        }
        this.inputTimer = null;
        this.resizeTimer = null;
        this.sessionTimer = null;
        this.sizeHintTimer = null;
        this.bellTimer = null;
        this.searchTimer = null;
    }

    /**
     * Report a call that failed, without declaring the session dead: the shell
     * is told to be gone by the session itself, over the bus, and a refused
     * call says nothing about it.
     *
     * @param {Error} error
     * @param {String} fallbackMessage
     */
    reportError(error, fallbackMessage) {
        const message = error?.data?.message || error?.message || fallbackMessage;
        this.notification.add(message, {type: "danger"});
    }
}

registry
    .category("actions")
    .add("cetmix_tower_server_terminal.terminal", TowerTerminalAction);
