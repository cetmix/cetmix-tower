/** @odoo-module **/

import {Component, onWillDestroy, useEffect, useRef, useState} from "@odoo/owl";

class AutocompletePopup extends Component {
    /**
     * Component setup method that initializes refs, state, and effects
     */
    setup() {
        this.popupRef = useRef("popupRef");
        this.searchInput = useRef("searchInput");
        this.itemsContainer = useRef("itemsContainer");

        // State for search functionality
        this.state = useState({
            searchTerm: "",
        });

        useEffect(
            () => {
                this.scrollToSelected();
            },
            () => [this.props.selectedIndex]
        );

        // Auto-focus search input when popup opens
        useEffect(
            () => {
                if (this.searchInput.el) {
                    // Use setTimeout to ensure DOM is ready
                    const timeoutId = setTimeout(() => {
                        this.searchInput.el.focus();
                    }, 0);
                    return () => clearTimeout(timeoutId);
                }
            },
            () => []
        );

        useEffect(
            () => {
                if (this.props.position) {
                    const timeoutId = setTimeout(() => {
                        if (this.popupRef.el) {
                            this.popupRef.el.style.left = `${this.props.position.left}px`;
                            this.popupRef.el.style.top = `${this.props.position.top}px`;
                            this.popupRef.el.style.position = "fixed";
                        }
                    }, 0);
                    return () => clearTimeout(timeoutId);
                }
            },
            () => [this.props.position]
        );

        onWillDestroy(() => {
            if (this.searchTimeout) {
                clearTimeout(this.searchTimeout);
            }
        });
    }

    /**
     * Updates search term from external keyboard input (from editor)
     * @param {String} char - The character typed or 'Backspace' for deletion
     */
    updateSearchFromEditor(char) {
        if (char === "Backspace") {
            this.state.searchTerm = this.state.searchTerm.slice(0, -1);
        } else if (char.length === 1) {
            this.state.searchTerm += char;
        }
        if (this.props.onSelectedIndexChange) {
            const newIndex = this.filteredCommands.length > 0 ? 0 : -1;
            this.props.onSelectedIndexChange(newIndex);
        }
    }

    /**
     * Filters commands based on search term with enhanced search capabilities
     * @returns {Array} Filtered and sorted array of commands matching the search term
     */
    get filteredCommands() {
        if (!this.state.searchTerm.trim()) {
            return this.props.commands || [];
        }

        const searchTerm = this.state.searchTerm.toLowerCase();

        const commands = this.props.commands || [];
        const scoredCommands = commands
            .map((command) => {
                const name = (command.name || "").toLowerCase();
                const reference = (command.reference || "").toLowerCase();

                let score = 0;

                // Exact matches get highest priority
                if (name === searchTerm || reference === searchTerm) {
                    score = 1000;
                }
                // Starts with search term gets high priority
                else if (
                    name.startsWith(searchTerm) ||
                    reference.startsWith(searchTerm)
                ) {
                    score = 100;
                }
                // Contains search term gets medium priority
                else if (name.includes(searchTerm) || reference.includes(searchTerm)) {
                    score = 10;
                }
                // No match
                else {
                    return null;
                }

                // Boost score for name matches over reference matches
                if (name.includes(searchTerm)) {
                    score += 5;
                }

                // Boost score for shorter matches (more relevant)
                score += Math.max(0, 50 - Math.min(name.length, reference.length));

                return {command, score};
            })
            .filter((item) => item !== null)
            .sort((a, b) => b.score - a.score)
            .map((item) => item.command);

        return scoredCommands;
    }

    /**
     * Debounces the search filtering
     * @param {String} searchTerm - The search term to set
     */
    debouncedSearch(searchTerm) {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        this.searchTimeout = setTimeout(() => {
            this.state.searchTerm = searchTerm;
            if (this.props.onSelectedIndexChange) {
                const newIndex = this.filteredCommands.length > 0 ? 0 : -1;
                this.props.onSelectedIndexChange(newIndex);
            }
        }, 150);
    }

    /**
     * Handles search input changes
     * @param {Event} ev - The input event
     */
    onSearchInput(ev) {
        ev.stopPropagation();
        this.debouncedSearch(ev.target.value);
    }

    /**
     * Common keyboard navigation logic
     * @param {KeyboardEvent} ev - The keyboard event
     */
    handleKeyboardNavigation(ev) {
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            const len = this.filteredCommands.length;
            if (len === 0) return;
            const current = this.props.selectedIndex ?? -1;
            const newIndex = Math.min(current + 1, len - 1);
            if (this.props.onSelectedIndexChange) {
                this.props.onSelectedIndexChange(newIndex);
            }
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            const len = this.filteredCommands.length;
            if (len === 0) return;
            const current = this.props.selectedIndex ?? -1;
            const newIndex = current <= 0 ? 0 : current - 1;
            if (this.props.onSelectedIndexChange) {
                this.props.onSelectedIndexChange(newIndex);
            }
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            const idx = this.props.selectedIndex ?? -1;
            if (idx >= 0) {
                const selectedCommand = this.filteredCommands[idx];
                this.onItemClick(selectedCommand);
            }
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.props.onItemClick(null);
        }
    }

    /**
     * Handles keydown events on search input
     * @param {KeyboardEvent} ev - The keyboard event
     */
    onSearchKeyDown(ev) {
        ev.stopPropagation();
        this.handleKeyboardNavigation(ev);
    }

    /**
     * Handles focus events on search input
     * @param {FocusEvent} ev - The focus event
     */
    onSearchFocus(ev) {
        ev.stopPropagation();
    }

    /**
     * Handles blur events on search input
     * @param {FocusEvent} ev - The blur event
     */
    onSearchBlur(ev) {
        ev.stopPropagation();
    }

    /**
     * Handles click events on search input
     * @param {MouseEvent} ev - The click event
     */
    onSearchClick(ev) {
        ev.stopPropagation();
    }

    /**
     * Handles mousedown events on search input
     * @param {MouseEvent} ev - The mousedown event
     */
    onSearchMouseDown(ev) {
        ev.stopPropagation();
    }

    /**
     * Handles item click events
     * @param {Object} command - The selected command object
     */
    onItemClick(command) {
        this.props.onItemClick(command);
    }

    /**
     * Handles close button click events
     */
    onCloseClick() {
        this.props.onItemClick(null);
    }

    /**
     * Scrolls the selected item into view
     */
    scrollToSelected() {
        const itemsContainer = this.itemsContainer.el;
        if (
            itemsContainer &&
            this.props.selectedIndex !== undefined &&
            this.props.selectedIndex >= 0 &&
            this.props.selectedIndex < itemsContainer.children.length
        ) {
            const selectedItem = itemsContainer.children[this.props.selectedIndex];
            if (selectedItem) {
                selectedItem.scrollIntoView({
                    block: "nearest",
                    behavior: "smooth",
                });
            }
        }
    }

    /**
     * Returns CSS class for autocomplete item based on selection state
     * @param {Number} index - The item index
     * @returns {String} CSS class string
     */
    getItemClass(index) {
        return index === (this.props.selectedIndex ?? -1)
            ? "ace-autocomplete-item ace-autocomplete-item-selected"
            : "ace-autocomplete-item";
    }
}

AutocompletePopup.template = "cetmix_tower_server.AutocompletePopup";
AutocompletePopup.props = {
    commands: {type: Array},
    onItemClick: {type: Function},
    position: {type: Object},
    selectedIndex: {type: Number, optional: true},
    onSelectedIndexChange: {type: Function, optional: true},
    type: {type: String, optional: true},
};

export {AutocompletePopup};
