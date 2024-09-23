odoo.define("cetmix_tower_server.server_state_field", function (require) {
    "use strict";

    var core = require("web.core");
    var registry = require("web.field_registry");
    var AbstractField = require("web.AbstractField");

    var qweb = core.qweb;

    var ServerStatusField = AbstractField.extend({
        template: "FormSelection",
        events: {
            "click .dropdown-item": "_setSelection",
        },
        supportedFieldTypes: ["selection"],

        /**
         * Returns the drop down button.
         *
         * @override
         */
        getFocusableElement: function () {
            return this.$("a[data-toggle='dropdown']");
        },

        isSet: function () {
            return true;
        },

        /**
         * Prepares the state values to be rendered using the FormSelection.Items template.
         *
         * @private
         */
        _prepareDropdownValues: function () {
            var _data = [];
            _.map(this.field.selection || [], function (selection_item) {
                var value = {
                    name: selection_item[0],
                    tooltip: selection_item[1],
                    state_name: selection_item[1],
                };
                value.state_class =
                    "o_server_status_" + value.name.toLowerCase().replace(/ /g, "_");
                _data.push(value);
            });
            _data.unshift({
                name: false,
                tooltip: "Undefined",
                state_name: "Undefined",
                state_class: "o_server_status_undefined",
            });
            this.possible_state_classes = _.uniq(
                _.map(_data, function (item) {
                    return item.state_class;
                })
            );
            return _data;
        },

        /**
         * This widget uses the FormSelection template but needs to customize it a bit.
         *
         * @private
         * @override
         */
        _render: function () {
            var states = this._prepareDropdownValues();

            // Handle the case where value is false and display "Undefined"
            var currentState =
                _.findWhere(states, {name: this.value}) ||
                _.findWhere(states, {name: false});

            this.$(".o_status_text").remove();
            this.$(".o_status")
                .removeClass(this.possible_state_classes.join(" "))
                .addClass(currentState.state_class)
                .prop("special_click", true)
                .parent()
                .attr("title", currentState.state_name)
                .attr("aria-label", this.string + ": " + currentState.state_name)
                .addClass("o_server_status_field")
                .prepend(
                    $("<span></span>", {class: "o_status_text"}).text(
                        currentState.state_name
                    )
                );

            var $items = $(
                qweb.render("FormSelection.items", {
                    states: _.without(states, currentState),
                })
            );
            var $dropdown = this.$(".dropdown-menu");
            $dropdown.children().remove();
            $items.appendTo($dropdown);

            // Handle the readonly mode to ensure dropdown is disabled when not in edit mode
            var isReadonly = this.record.evalModifiers(this.attrs.modifiers).readonly;
            this.$("a[data-toggle=dropdown]").toggleClass(
                "disabled",
                isReadonly || false
            );
        },

        /**
         * Intercepts the click on the FormSelection.Item to set the widget value.
         *
         * @private
         * @param {MouseEvent} ev
         */
        _setSelection: function (ev) {
            ev.preventDefault();
            var $item = $(ev.currentTarget);
            var value = String($item.data("value"));
            this._setValue(value === "false" ? false : value); // Adjust for 'false' as string
            if (this.mode === "edit") {
                this._render();
            }
        },
    });

    registry.add("server_status", ServerStatusField);
});
