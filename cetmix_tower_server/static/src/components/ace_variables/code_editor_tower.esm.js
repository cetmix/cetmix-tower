/** @odoo-module **/

import {onWillDestroy, useEffect, useState} from "@odoo/owl";
import {AutocompletePopup} from "./autocomplete_popup.esm";
import {CodeEditor} from "@web/core/code_editor/code_editor";
import {useService} from "@web/core/utils/hooks";

const POPUP_FALLBACK_WIDTH = 500;
const POPUP_FALLBACK_HEIGHT = 300;

export class CodeEditorTower extends CodeEditor {
    static template = "cetmix_tower_server.CodeEditorTower";
    static components = {
        AutocompletePopup,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.inputListener = null;
        this.clickOutsideListener = null;
        this.inputTimeout = null;
        this.clickOutsideTimeout = null;
        this.variables = [];
        this.secrets = [];

        this.state = useState({
            showPopup: false,
            popupItems: [],
            popupPosition: {},
            selectedIndex: 0,
            // Add popup type to distinguish between variables and secrets
            popupType: "variables",
        });

        this.updateSelectedIndex = this.updateSelectedIndex.bind(this);

        useEffect(
            (el) => {
                if (!el) {
                    return;
                }

                // Keep in closure
                const aceEditor = window.ace.edit(el);
                this.aceEditor = aceEditor;

                const session = aceEditor.getSession();
                this.setupCustomAutocompletion(aceEditor, session);
                return () => {
                    if (aceEditor) {
                        aceEditor.destroy();
                    }
                };
            },
            () => [this.editorRef.el]
        );

        onWillDestroy(() => {
            if (this.inputTimeout) {
                clearTimeout(this.inputTimeout);
            }
            if (this.clickOutsideTimeout) {
                clearTimeout(this.clickOutsideTimeout);
            }
            if (this.aceEditor && this.inputListener) {
                this.aceEditor.getSession().off("change", this.inputListener);
            }
            this.hideAutocompletePopup();
        });
    }

    async loadVariables() {
        try {
            this.variables = await this.orm.searchRead(
                "cx.tower.variable",
                [],
                ["name", "reference"]
            );
        } catch (error) {
            console.error("Failed to load variables for autocomplete:", error);
            this.variables = [];
            this.env.services.notification.add(
                "Failed to load autocomplete variables",
                {type: "warning"}
            );
        }
    }

    /**
     * Load secrets from the backend using ORM service
     * @returns {Promise<void>}
     */
    async loadSecrets() {
        try {
            this.secrets = await this.orm.searchRead(
                "cx.tower.key",
                [["key_type", "=", "s"]],
                ["name", "reference"]
            );
        } catch (error) {
            console.error("Failed to load secrets for autocomplete:", error);
            this.secrets = [];
            this.env.services.notification.add("Failed to load autocomplete secrets", {
                type: "warning",
            });
        }
    }

    /**
     * Configure custom autocompletion commands and keyboard bindings for ACE editor
     * @param {Object} aceEditor - The ACE editor instance
     * @param {Object} session - The ACE editor session
     */
    setupCustomAutocompletion(aceEditor, session) {
        // Remove any existing conflicting commands first
        aceEditor.commands.removeCommand("startAutocomplete");
        aceEditor.commands.removeCommand("expandSnippet");

        // Only add the main autocomplete trigger command
        aceEditor.commands.addCommand({
            name: "customAutoComplete",
            bindKey: {win: "Ctrl-Space", mac: null},
            exec: (editor) => {
                this.showCustomCompletions(editor);
                return true;
            },
        });

        // Set up input listener for {{ and #! triggers
        this.inputListener = () => {
            // Clear any existing timeout
            if (this.inputTimeout) {
                clearTimeout(this.inputTimeout);
            }
            // Use setTimeout to ensure the text is fully processed
            this.inputTimeout = setTimeout(() => {
                const cursor = aceEditor.getCursorPosition();
                const line = session.getLine(cursor.row);
                const textBeforeCursor = line.substring(0, cursor.column);

                // Check for variables trigger {{
                if (textBeforeCursor.endsWith("{{")) {
                    // Remove {{ symbols from editor
                    const startColumn = Math.max(0, cursor.column - 2);
                    const range = {
                        start: {row: cursor.row, column: startColumn},
                        end: {row: cursor.row, column: cursor.column},
                    };
                    session.replace(range, "");

                    // Update cursor position
                    const newCursor = {
                        row: cursor.row,
                        column: startColumn,
                    };
                    aceEditor.moveCursorToPosition(newCursor);
                    this.showCustomCompletions(aceEditor, "variables");
                }
                // Check for secrets trigger #!
                else if (textBeforeCursor.endsWith("#!")) {
                    // Remove !# symbols from editor
                    const startColumn = Math.max(0, cursor.column - 2);
                    const range = {
                        start: {row: cursor.row, column: startColumn},
                        end: {row: cursor.row, column: cursor.column},
                    };
                    session.replace(range, "");

                    // Update cursor position
                    const newCursor = {
                        row: cursor.row,
                        column: startColumn,
                    };
                    aceEditor.moveCursorToPosition(newCursor);
                    this.showCustomCompletions(aceEditor, "secrets");
                }
            }, 10);
        };

        session.on("change", this.inputListener);
    }

    /**
     * Show custom completions popup with available variables or secrets
     * @param {Object} editor - ACE editor instance
     * @param {String} type - Type of completion ('variables' or 'secrets')
     * @returns {Promise<void>}
     */
    async showCustomCompletions(editor, type = "variables") {
        const cursor = editor.getCursorPosition();
        const session = editor.getSession();
        const line = session.getLine(cursor.row);
        const textBeforeCursor = line.substring(0, cursor.column);

        let items = [];
        let triggerLength = 0;

        if (type === "secrets") {
            // Handle secrets
            await this.loadSecrets();

            if (!this.secrets.length) {
                return;
            }

            items = this.secrets;
        } else {
            // Handle variables
            await this.loadVariables();

            if (!this.variables.length) {
                return;
            }

            items = this.variables;
            // Check if we're already in a variable context
            const isInVariableContext = textBeforeCursor.endsWith("{{");

            if (isInVariableContext) {
                triggerLength = 2;
            }
        }

        const position = this.calculatePopupPosition(editor, cursor);

        // Set popup type in state
        this.state.popupType = type;

        await this.showAutocompletePopup(items, position, editor, triggerLength, type);
    }

    /**
     * Calculate the optimal position for the autocomplete popup
     * @param {Object} editor - ACE editor instance
     * @param {Object} cursor - Cursor position object
     * @returns {Object} Position object with left and top coordinates
     */
    calculatePopupPosition(editor, cursor) {
        const renderer = editor.renderer;

        // Calculate cursor position within the editor
        const cursorPixelPos = renderer.textToScreenCoordinates(
            cursor.row,
            cursor.column
        );

        // Get scroll position
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

        // Calculate the cursor position relative to the viewport
        const viewportLeft = cursorPixelPos.pageX - scrollLeft;
        const viewportTop = cursorPixelPos.pageY - scrollTop;

        // Position popup just below the cursor
        const finalLeft = viewportLeft;
        const finalTop = viewportTop + renderer.lineHeight;

        // Ensure popup doesn't go outside viewport
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const popup = document.querySelector(".ace-autocomplete-popup");
        const popupWidth = popup ? popup.offsetWidth : POPUP_FALLBACK_WIDTH;
        const popupHeight = popup ? popup.offsetHeight : POPUP_FALLBACK_HEIGHT;

        let adjustedLeft = finalLeft;
        let adjustedTop = finalTop;

        // Adjust if popup would go off-screen horizontally
        if (finalLeft + popupWidth > viewportWidth) {
            adjustedLeft = finalLeft - popupWidth;
        }

        // Adjust if popup would go off-screen vertically
        if (finalTop + popupHeight > viewportHeight) {
            adjustedTop = finalTop - popupHeight - renderer.lineHeight;
        }

        // Make sure popup is not positioned off-screen
        adjustedLeft = Math.max(0, adjustedLeft);
        adjustedTop = Math.max(0, adjustedTop);

        return {
            left: adjustedLeft,
            top: adjustedTop,
        };
    }

    /**
     * Display the autocomplete popup with variables or secrets at the specified position
     * @param {Array} items - Array of available variables or secrets
     * @param {Object} position - Position object with left and top coordinates
     * @param {Object} editor - ACE editor instance
     * @param {Number} triggerLength - Length of trigger text that should be replaced
     * @param {String} type - Type of completion ('variables' or 'secrets')
     * @returns {Promise<void>}
     */
    async showAutocompletePopup(
        items,
        position,
        editor,
        triggerLength,
        type = "variables"
    ) {
        this.hideAutocompletePopup();

        this.state.popupItems = items;
        this.state.popupPosition = position;
        this.state.showPopup = true;
        this.state.selectedIndex = 0;
        this.state.popupType = type;
        this.currentEditor = editor;
        this.currentTriggerLength = triggerLength;
        this.currentType = type;

        // Add click outside listener
        this.clickOutsideListener = (event) => {
            // Check if click is outside the popup and ace editor
            const popupElement = document.querySelector(".ace-autocomplete-popup");
            const aceElement = this.aceEditor.container;

            if (
                popupElement &&
                !popupElement.contains(event.target) &&
                aceElement &&
                !aceElement.contains(event.target)
            ) {
                this.hideAutocompletePopup();
            }
        };

        // Store timeout ID to prevent race condition
        this.clickOutsideTimeout = setTimeout(() => {
            // Guard against race condition: only register if popup is still shown
            if (this.state.showPopup) {
                document.addEventListener("click", this.clickOutsideListener, true);
            }
            this.clickOutsideTimeout = null;
        }, 0);
    }

    /**
     * Hide the autocomplete popup and clean up event listeners
     */
    hideAutocompletePopup() {
        // Clear pending timeout to prevent race condition
        if (this.clickOutsideTimeout) {
            clearTimeout(this.clickOutsideTimeout);
            this.clickOutsideTimeout = null;
        }

        // Remove click outside listener
        if (this.clickOutsideListener) {
            document.removeEventListener("click", this.clickOutsideListener, true);
            this.clickOutsideListener = null;
        }

        this.state.showPopup = false;
        this.state.popupItems = [];
        this.currentEditor = null;
        this.state.selectedIndex = 0;

        // Return focus to the ACE editor
        if (this.aceEditor) {
            this.aceEditor.focus();
        }
    }

    /**
     * Update the selected index in the autocomplete popup
     * @param {Number} index - New selected index
     */
    updateSelectedIndex(index) {
        if (this.state) {
            this.state.selectedIndex = index;
        }
    }

    /**
     * Handle selection of a command from the autocomplete popup
     * @param {Object} command - Selected command object
     * @param {Object} editor - ACE editor instance
     */
    handleCommandSelection(command, editor) {
        if (!command || !command.reference) {
            this.hideAutocompletePopup();
            return;
        }

        const cursor = editor.getCursorPosition();
        const session = editor.getSession();
        const line = session.getLine(cursor.row);
        const textBeforeCursor = line.substring(0, cursor.column);

        // Get line length for validation
        const lineLength = session.getLine(cursor.row).length;
        const currentType = this.currentType || this.state.popupType;

        let range = null;
        let insertText = "";

        if (currentType === "secrets") {
            // Handle secrets insertion
            // Check if we're inside a secret context (between #!cxtower.secret and !#)
            const lastSecretStart = textBeforeCursor.lastIndexOf("#!cxtower.secret");
            const lastSecretEnd = textBeforeCursor.lastIndexOf("!#");

            // Count occurrences of start and end delimiters for more robust validation
            const startCount = (textBeforeCursor.match(/#!cxtower\.secret/g) || [])
                .length;
            const endCount = (textBeforeCursor.match(/!#/g) || []).length;
            const isInsideSecret =
                startCount > endCount &&
                lastSecretStart > lastSecretEnd &&
                lastSecretStart !== -1;

            if (isInsideSecret) {
                // We're inside a secret context, replace from after #!cxtower to cursor
                range = {
                    start: {row: cursor.row, column: lastSecretStart + 16},
                    end: {row: cursor.row, column: cursor.column},
                };
                // Clamp range to valid bounds
                range.start.column = Math.max(
                    0,
                    Math.min(range.start.column, lineLength)
                );
                range.end.column = Math.max(
                    range.start.column,
                    Math.min(range.end.column, lineLength)
                );
                insertText = `${command.reference}!#`;
            } else {
                // We're not in a secret context, insert complete secret
                const triggerLength = this.currentTriggerLength || 0;
                range = {
                    start: {row: cursor.row, column: cursor.column - triggerLength},
                    end: {row: cursor.row, column: cursor.column},
                };
                // Clamp range to valid bounds
                range.start.column = Math.max(
                    0,
                    Math.min(range.start.column, lineLength)
                );
                range.end.column = Math.max(
                    range.start.column,
                    Math.min(range.end.column, lineLength)
                );
                insertText = `#!cxtower.secret.${command.reference}!#`;
            }
        } else {
            // Handle variables insertion (existing logic)
            const lastOpenBrace = textBeforeCursor.lastIndexOf("{{");
            const lastCloseBrace = textBeforeCursor.lastIndexOf("}}");
            const isInsideVariable =
                lastOpenBrace > lastCloseBrace && lastOpenBrace !== -1;

            if (isInsideVariable) {
                // We're inside a variable context, replace from after {{ to cursor
                range = {
                    start: {row: cursor.row, column: lastOpenBrace + 2},
                    end: {row: cursor.row, column: cursor.column},
                };
                // Clamp range to valid bounds
                range.start.column = Math.max(
                    0,
                    Math.min(range.start.column, lineLength)
                );
                range.end.column = Math.max(
                    range.start.column,
                    Math.min(range.end.column, lineLength)
                );
                insertText = ` ${command.reference} `;
            } else {
                // We're not in a variable context, insert complete variable
                const triggerLength = this.currentTriggerLength || 0;
                range = {
                    start: {row: cursor.row, column: cursor.column - triggerLength},
                    end: {row: cursor.row, column: cursor.column},
                };
                // Clamp range to valid bounds
                range.start.column = Math.max(
                    0,
                    Math.min(range.start.column, lineLength)
                );
                range.end.column = Math.max(
                    range.start.column,
                    Math.min(range.end.column, lineLength)
                );
                insertText = `{{ ${command.reference} }}`;
            }
        }

        // Replace the text
        session.replace(range, insertText);

        // Get the updated line length after replacement
        const updatedLineLength = session.getLine(cursor.row).length;

        // Position cursor after the inserted text
        const newCursor = {
            row: cursor.row,
            column: range.start.column + insertText.length,
        };

        newCursor.column = Math.max(0, Math.min(newCursor.column, updatedLineLength));

        editor.moveCursorToPosition(newCursor);

        this.hideAutocompletePopup();
        editor.focus();
    }
}
