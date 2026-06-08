odoo.define('oql.oql_editor_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    // Module-level variable to capture the last click coordinates on an
    // OQL editor cell. When the list view recreates the widget on mode
    // switch, this preserves the click position so we can place the cursor
    // where the user actually clicked.
    var _lastClickX = null;
    var _lastClickY = null;

    var OQLEditor = AbstractField.extend({
        className: 'o_oql_editor',
        supportedFieldTypes: ['char', 'text'],

        /**
         * Tell the list view this widget is quick-editable (click to edit).
         */
        isQuickEditable: true,

        init: function (parent, name, record, options) {
            this._super.apply(this, arguments);
            this.model = record.model;
            this.res_id = record.res_id;
            this._editorReady = false;
            this._pendingMode = null;
            this._needsFocus = false;
        },

        start: function () {
            var self = this;
            var def = this._super.apply(this, arguments);
            return $.when(def).then(function () {
                var editorDef = $.Deferred();
                self._initEditor().then(function () {
                    editorDef.resolve();
                }).catch(function (err) {
                    console.error('[OQL] Editor init failed:', err);
                    editorDef.reject(err);
                });
                return editorDef;
            });
        },

        /**
         * Override focus() to forward to CodeMirror.
         */
        focus: function () {
            if (this.oqlEditor && this.oqlEditor.editor) {
                this.oqlEditor.focus();
            }
        },

        /**
         * Called by the list view when a cell is selected for editing.
         */
        activate: function (edit) {
            if (!edit) return false;
            if (this.oqlEditor && this.oqlEditor.editor) {
                var self = this;
                requestAnimationFrame(function () {
                    if (self.oqlEditor && self.oqlEditor.editor) {
                        self.oqlEditor.focus();
                    }
                });
                return true;
            }
            this._needsFocus = true;
            return true;
        },

        /**
         * Return a focusable element for the list view's focus mechanism.
         */
        getFocusableElement: function () {
            return this.$input || $();
        },

        // ==========================================
        // Rendering
        // ==========================================

        _renderEdit: function () {
            if (!this._editorReady) {
                this._pendingMode = 'edit';
                return;
            }
            this._applyMode('edit');
        },

        _renderReadonly: function () {
            if (!this._editorReady) {
                this._pendingMode = 'readonly';
                return;
            }
            this._applyMode('readonly');
        },

        /**
         * Apply the correct mode to the CodeMirror editor.
         * @private
         */
        _applyMode: function (mode) {
            if (!this.oqlEditor || !this.oqlEditor.editor) return;

            var isReadonly = (mode === 'readonly');

            this.oqlEditor.setReadonly(isReadonly);

            // Re-sync the value from the record, but only if it differs
            // from the current editor value. This prevents resetting the
            // cursor position when the value hasn't changed.
            var currentValue = this.oqlEditor.getValue();
            if (this.value !== undefined && this.value !== null && currentValue !== this.value) {
                this.oqlEditor.setValue(this.value);
            }

            if (!isReadonly) {
                this._ensureFocusProxy();
            }

            // CRITICAL: Delay refresh() and cursor placement to the next
            // animation frame. CodeMirror needs the widget's $el to be in
            // the DOM and laid out (offsetHeight > 0) before refresh() can
            // render content, and before coordsChar() can work.
            var self = this;
            requestAnimationFrame(function () {
                if (!self.oqlEditor || !self.oqlEditor.editor) return;
                self.oqlEditor.refresh();

                if (!isReadonly) {
                    var cm = self.oqlEditor.editor;
                    // Try to place cursor at the click position using the
                    // captured coordinates. coordsChar() only works after
                    // refresh() when the editor is fully laid out.
                    if (_lastClickX !== null && _lastClickY !== null) {
                        try {
                            var pos = cm.coordsChar({ left: _lastClickX, top: _lastClickY });
                            if (pos && pos.line !== undefined) {
                                cm.setCursor(pos);
                            }
                        } catch (e) {
                            // coordsChar can fail; fall through to default
                        }
                        _lastClickX = null;
                        _lastClickY = null;
                    } else {
                        // No click coordinates (keyboard navigation).
                        // If cursor is at (0,0) and content exists, move to end.
                        var cursor = cm.getCursor();
                        if (cursor.line === 0 && cursor.ch === 0 && cm.getValue().length > 0) {
                            var lastLine = cm.lastLine();
                            cm.setCursor(lastLine, cm.getLine(lastLine).length);
                        }
                    }
                }
            });
        },

        // ==========================================
        // Value management (AbstractField interface)
        // ==========================================

        /**
         * Return the current editor value.
         */
        _getValue: function () {
            if (this.oqlEditor && this.oqlEditor.editor) {
                return this.oqlEditor.getValue();
            }
            return this.value || '';
        },

        /**
         * Commit the current value to the record.
         * Only called on blur (when user finishes editing).
         * @private
         */
        _commitValue: function () {
            var newValue = this._getValue();
            if (newValue !== this.value) {
                this._setValue(newValue);
            }
        },

        // ==========================================
        // Editor initialization
        // ==========================================

        _initEditor: function () {
            var self = this;
            var options = this.nodeOptions || {};
            var isReadonly = this.mode === 'readonly';

            // Capture click coordinates on the widget's $el so that when the
            // list view recreates the widget on mode switch, we can place the
            // cursor at the click position in the new CodeMirror instance.
            this.$el.on('mousedown.oql_editor_cell', function (e) {
                _lastClickX = e.clientX;
                _lastClickY = e.clientY;
            });

            this.oqlEditor = new window.OQLEditorCore($.extend({}, options, {
                container: this.$el,
                model: options.model || this.model,
                res_id: options.res_id || this.res_id,
                fieldName: this.name,
                readonly: isReadonly,
                hintMethod: options.hintMethod || 'hinto',
                onChange: function () {
                    // Do NOT commit value on every keystroke.
                    // Only commit when the editor loses focus (blur event below).
                }
            }));

            return this.oqlEditor.start().then(function () {
                self._editorReady = true;

                // Set initial value
                if (self.value !== undefined && self.value !== null) {
                    self.oqlEditor.setValue(self.value);
                }

                // Set up focus proxy for list view
                self._ensureFocusProxy();

                // ---- Event listeners ----

                // 1. Blur: commit value, but NOT when hint popup is open
                //    (selecting a hint causes a temporary blur)
                self.oqlEditor.editor.on('blur', function () {
                    setTimeout(function () {
                        if (document.querySelector('.CodeMirror-hints')) {
                            return;
                        }
                        self._commitValue();
                    }, 150);
                });

                // 2. Mousedown on CodeMirror: stop propagation to prevent
                //    the list view from stealing the event. CodeMirror handles
                //    cursor positioning on mousedown itself.
                var cmWrapper = self.oqlEditor.editor.getWrapperElement();
                $(cmWrapper).on('mousedown.oql_editor', function (e) {
                    if (!self.oqlEditor.readonly) {
                        e.stopPropagation();
                    }
                });

                // 3. Keydown: prevent keys from propagating to the list view
                //    (which would add a new row on Enter).
                $(cmWrapper).on('keydown.oql_editor', function (e) {
                    if (!self.oqlEditor.readonly) {
                        e.stopPropagation();
                    }
                });

                // Apply any render that was deferred while the editor was initializing
                if (self._pendingMode) {
                    self._applyMode(self._pendingMode);
                    self._pendingMode = null;
                }

                // If activate() was called before the editor was ready,
                // focus the editor now
                if (self._needsFocus) {
                    self._needsFocus = false;
                    requestAnimationFrame(function () {
                        if (self.oqlEditor && self.oqlEditor.editor) {
                            self.oqlEditor.focus();
                        }
                    });
                }
            });
        },

        /**
         * Ensure the hidden $input focus proxy exists.
         * Needed for list view's focus mechanism (getFocusableElement).
         * @private
         */
        _ensureFocusProxy: function () {
            if (this.$input) return;
            var self = this;
            this.$input = $('<input type="text" style="position:absolute;opacity:0;width:1px;height:1px;pointer-events:none;tabindex:0">');
            this.$el.append(this.$input);
            this.$input.on('focus', function () {
                if (self.oqlEditor && self.oqlEditor.editor) {
                    self.oqlEditor.focus();
                }
            });
        },

        /**
         * Clean up on destroy.
         */
        destroy: function () {
            if (this.oqlEditor) {
                this.oqlEditor.destroy();
                this.oqlEditor = null;
            }
            this._super.apply(this, arguments);
        },
    });

    fieldRegistry.add('oql_editor', OQLEditor);
    return OQLEditor;
});
