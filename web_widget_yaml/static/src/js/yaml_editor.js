odoo.define('web_widget_yaml.YamlEditor', function (require) {
    "use strict";

    var fieldRegistry = require('web.field_registry');
    var basic_fields = require('web.basic_fields');
    var AceEditor = basic_fields.AceEditor;

    var YamlEditor = AceEditor.extend({
        /**
         * We override the init to ensure our library is in the list
         * before the widget tries to load its dependencies.
         */
        init: function (parent, name, record, options) {
            this._super.apply(this, arguments);

            // Set default mode.
            this.nodeOptions.mode = this.nodeOptions.mode || 'yaml';

            // Add custom path to the nested array of libs
            // The [1] index is where Odoo stores the mode files
            var yamlPath = '/web/static/lib/ace/mode-yaml.js';
            if (!this.jsLibs[1].includes(yamlPath)) {
                this.jsLibs[1].push(yamlPath);
            }
        },

        _startAce: function () {
            this._super.apply(this, arguments);

            // 1. Create a copy so we don't modify the original Odoo object
            var aceOptions = _.clone(this.nodeOptions);

            // 2. Remove the 'mode' key
            delete aceOptions.mode;

            // 3. Apply the remaining options (like fontSize)
            this.aceEditor.setOptions(aceOptions);
        },
    });


    fieldRegistry.add('yaml', YamlEditor);
    return YamlEditor;
});
