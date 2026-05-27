odoo.define('oql.oql_editor_widget', function (require) {
    "use strict";

    const DebouncedField = require('web.basic_fields').DebouncedField;
    const fieldRegistry = require('web.field_registry');

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
            var self = this;
            var def = this._super.apply(this, arguments);
            return $.when(def).then(function () {
                return self._initEditor();
            });
        },

        /**
         * Override default focus() so the tree's cell-focus cycle
         * forwards to CodeMirror instead of a non-existent $input.
         */
        focus: function () {
            if (this.oqlEditor && this.oqlEditor.editor) {
                this.oqlEditor.focus();
            }
        },

        /**
         * Tree view calls widget.activate() → getFocusableElement() → focus().
         * We must return the hidden $input so the tree can find & focus it,
         * then our focus handler redirects to CodeMirror.
         */
        getFocusableElement: function () {
            return this.$input || $();
        },

        // Preserve CodeMirror across re-renders (e.g. after form save)
        _renderEdit: function () {
            if (this.oqlEditor && this.oqlEditor.editor && this.$el.find('.CodeMirror').length) {
                // Editor already exists: sync value and refresh
                if (this.value !== undefined) {
                    this.oqlEditor.setValue(this.value);
                }
                this.oqlEditor.refresh();
                return;
            }
            // First render: DON'T call _super() — parent's _renderEdit would
            // replace the DOM and create a native $input that would steal focus.
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
            var options = this.nodeOptions || {};

            // Create a hidden input so the tree's focus mechanism
            // finds something to focus, then redirect to CodeMirror
            if (!this.isReadonly) {
                this.$input = $('<input type="text" style="position:absolute;opacity:0;width:1px;height:1px;pointer-events:none;tabindex:0">');
                this.$el.append(this.$input);
                this.$input.on('focus', function () {
                    if (self.oqlEditor && self.oqlEditor.editor) {
                        self.oqlEditor.focus();
                    }
                });
            }

            this.oqlEditor = new window.OQLEditorCore({
                container: this.$el,
                model: options.model || this.model,
                res_id: options.res_id || this.res_id,
                fieldName: this.name,
                readonly: this.isReadonly,
                lineNumbers: options.line_numbers !== undefined ? options.line_numbers : true,
                hintMethod: options.hint_method || 'hinto',
                onChange: function (value) {
                    self._notifyChanges();
                }
            });

            // Start first, then set value (editor must exist for setValue)
            return this.oqlEditor.start().then(function () {
                if (self.value) {
                    self.oqlEditor.setValue(self.value);
                }
            });
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