odoo.define('web_widget_pill_icon.PillIconWidget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var field_registry = require('web.field_registry');

    var PillIconWidget = AbstractField.extend({
        supportedFieldTypes: ['char', 'selection', 'integer', 'float', 'many2one'],

        // Force the widget to stay in readonly mode even if the form is edited
        _renderEdit: function () {
            this._renderReadonly();
        },

        _renderReadonly: function () {
            var value = this.value;
            if (value === undefined || value === null || value === false || value === "") {
                return this.$el.empty();
            }

            var options = this.nodeOptions || {};
            var baseConfig = options.base || ''; // e.g. "pill outline sm"
            var valueMapping = options.values || {}; // e.g. "create": "fa-plus success"

            // Get value-specific config
            var configString = valueMapping[value] || '';

            // Extract FontAwesome
            var iconMatches = configString.match(/fa-[a-z0-9_-]+/g);
            var iconClass = iconMatches ? iconMatches[0] : '';

            // Remove icon from string to get semantic classes (e.g. "success")
            var semanticClasses = configString.replace(iconClass, '').trim();

            // Create the widget container with the root class + user configs
            var $container = $('<div>', {
                class: ('o_pill_icon_widget ' + baseConfig + ' ' + semanticClasses).trim()
            });

            // Build Internal Content
            if (iconClass) {
                $container.append($('<i>', { class: 'fa ' + iconClass + ' mr-1' }));
            }

            var displayText = this.field.type === 'selection' ?
                (this.field.selection.find(s => s[0] === value) || [value, value])[1] :
                this._formatValue(value);

            $container.append($('<span>', { text: displayText }));
            this.$el.empty().append($container);
        }
    });

    field_registry.add('pill_icon', PillIconWidget);
    return PillIconWidget;
});
