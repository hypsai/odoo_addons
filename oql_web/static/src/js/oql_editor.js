odoo.define('oql.oql_editor', function (require) {
    "use strict";

    const DebouncedField = require('web.basic_fields').DebouncedField;
    const fieldRegistry = require('web.field_registry');
    const OQLEditorCore = require('oql_web.oql_editor_core');

    const OQLEditor = DebouncedField.extend({
        className: 'o_oql_editor',
        supportedFieldTypes: ['char', 'text'],

        init: function (parent, name, record, options) {
            this._super.apply(this, arguments);
            this.model = record.model;
            this.res_id = record.res_id;
            this.isReadonly = this.mode === 'readonly';
        },

        start: function () {
            this._super.apply(this, arguments);
            return this._initEditor();
        },

        _getValue: function () {
            if (this.oqlEditor) {
                return this.oqlEditor.getValue();
            }
            return this.value;
        },

        _notifyChanges() {
            this.isDirty = !this._isLastSetValue(this._getValue());
            this._doDebouncedAction();
        },

        _initEditor: function () {
            var self = this;
            
            // Create OQL Editor Core instance
            this.oqlEditor = new OQLEditorCore({
                container: this.$el,
                model: this.model,
                res_id: this.res_id,
                fieldName: this.name,
                readonly: this.isReadonly,
                lineNumbers: true,
                onChange: function (value) {
                    self._notifyChanges();
                }
            });
            
            // Set initial value
            if (this.value) {
                this.oqlEditor.setValue(this.value);
            }
            
            // Start the editor
            return this.oqlEditor.start();
        },

        

        _onKeydown: function (e) {
            if (this.isReadonly) {
                return;
            }
            // Keep this function to stop 'Tab' from switching focus to another control.
        },
    });

    fieldRegistry.add('oql_editor', OQLEditor);
    return OQLEditor;
});