/**
 * OQL Search Bar - Odoo 15 version using patch()
 */
odoo.define('oql_web.oql_search_bar', function (require) {
    "use strict";

    var SearchBar = require('web.SearchBar');
    var ajax = require('web.ajax');
    var patch = require('web.utils').patch;
    var OQLEditorCore = require('oql_web.oql_editor_core');
    var session = require('web.session');
    
    // Storage keys
    var STORAGE_KEYS = {
        TOGGLE_STATE: 'oql_toggle_state_',
        HISTORY: 'oql_search_history_'
    };
    
    // Max history items
    var MAX_HISTORY = 50;

    // Constants
    var SELECTORS = {
        SEARCH_VIEW: '.o_searchview',
        SEARCH_BOX: '.o_searchview_input_container',
        TOGGLE_BTN: '.o_oql_toggle_btn'
    };

    var STYLES = {
        FLEX_CONTAINER: {
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'nowrap',
            width: '100%'
        },
        FLEX_ITEM: {
            flex: '1',
            minWidth: '0'
        },
        BUTTON: {
            marginRight: '5px',
            flexShrink: '0'
        }
    };

    // Extend SearchBar using patch()
    patch(SearchBar.prototype, 'oql_web.SearchBar', {
        /**
         * Initialize OQL state and add button after component is mounted
         */
        mounted: function () {
            this._super.apply(this, arguments);
            
            // Add OQL state
            this.oqlEnabled = false;
            this.oqlEditor = null;
            this.oqlHistory = this._loadHistory();
            
            // Add OQL button to DOM
            this._addOQLButton();
            
            // Restore toggle state
            this._restoreToggleState();
        },

        willUnmount: function () {
            this._super.apply(this, arguments);
            
            // Cleanup OQL editor if exists
            if (this.oqlEditor) {
                this.oqlEditor.destroy();
                this.oqlEditor = null;
            }
        },

        /**
         * Add OQL toggle button to the search bar
         * @private
         */
        _addOQLButton: function () {
            var self = this;
            var $searchView = $(this.el).closest(SELECTORS.SEARCH_VIEW);
            
            if ($searchView.length === 0) {
                console.warn('[OQL] Search view not found');
                return;
            }
            
            var $searchBox = $searchView.find(SELECTORS.SEARCH_BOX);
            if ($searchBox.length === 0) {
                console.warn('[OQL] Search box not found');
                return;
            }
            
            // Check if button already exists
            if ($searchView.parent().find(SELECTORS.TOGGLE_BTN).length > 0) {
                return;
            }
            
            // Setup flex container
            var $parent = $searchView.parent();
            Object.assign($parent[0].style, STYLES.FLEX_CONTAINER);
            
            // Create and insert button BEFORE the search view
            var $btn = $('<button class="btn btn-sm o_oql_toggle_btn" type="button">' +
                         '<i class="fa fa-code"></i> OQL</button>');
            Object.assign($btn[0].style, STYLES.BUTTON);
            $searchView.before($btn);
            
            // Make search view take remaining space
            Object.assign($searchView[0].style, STYLES.FLEX_ITEM);
            
            // Add editor container AFTER the search box
            var $editorDiv = $('<div class="o_oql_editor_container" style="display:none;width:100%;"></div>');
            $searchBox.after($editorDiv);
            
            // Toggle button click handler
            $btn.on('click', function () {
                self._toggleOQL($btn, $searchBox, $editorDiv);
            });
            
            console.log('[OQL] Button added successfully');
        },

        /**
         * Toggle OQL mode on/off
         * @private
         */
        _toggleOQL: function ($btn, $searchBox, $editorDiv) {
            var self = this;
            this.oqlEnabled = !this.oqlEnabled;
            
            if (this.oqlEnabled) {
                // Switch to OQL mode
                $btn.addClass('active');
                $searchBox.hide();
                $editorDiv.show();
                
                if (!this.oqlEditor) {
                    this._initOQLEditor($editorDiv);
                } else {
                    this.oqlEditor.focus();
                }
            } else {
                // Switch back to normal search
                $btn.removeClass('active');
                $searchBox.show();
                $editorDiv.hide();
                
                if (this.oqlEditor) {
                    this.oqlEditor.destroy();
                    this.oqlEditor = null;
                    $editorDiv.empty();
                }
            }
            
            // Save toggle state
            this._saveToggleState();
        },

        /**
         * Initialize OQL Editor using OQLEditorCore
         * @private
         */
        _initOQLEditor: function ($container) {
            var self = this;
            var model = this.model.config.modelName;
            
            if (!model) {
                console.error('[OQL] No model found');
                return;
            }
            
            // Wrap container for combobox layout
            var $wrapper = $('<div class="oql_combobox_wrapper" style="position: relative; display: flex; align-items: center; width: 100%;"></div>');
            $container.append($wrapper);
            
            // Create editor container inside wrapper
            var $editorContainer = $('<div style="flex: 1; min-width: 0;"></div>');
            $wrapper.append($editorContainer);
            
            // Create OQL Editor Core instance
            this.oqlEditor = new OQLEditorCore({
                container: $editorContainer,
                model: model,
                res_id: null,  // Search bar mode doesn't have a record ID
                fieldName: null,  // Search bar mode doesn't have a field name
                readonly: false,
                lineNumbers: false,
                history: this.oqlHistory,  // Pass history to core
                onSearch: function (query) {
                    self._doOQLSearch(query);
                },
                onHistorySelect: function (query) {
                    // Trigger search when history item is selected
                    self._doOQLSearch(query);
                }
            });
            
            // Start the editor
            this.oqlEditor.start().then(function () {
                self.oqlEditor.focus();
                
                // Add focus/blur handlers to update button border
                self.oqlEditor.editor.on('focus', function () {
                    $wrapper.addClass('oql-focused');
                });
                self.oqlEditor.editor.on('blur', function () {
                    $wrapper.removeClass('oql-focused');
                });
                
                // Add history button after editor is ready
                self._addHistoryButton($wrapper);
            });
        },

        /**
         * Add history button at the right end of OQL editor
         * @param {jQuery} $wrapper Wrapper container
         * @private
         */
        _addHistoryButton: function ($wrapper) {
            var self = this;
            
            // Check if history button already exists
            if ($wrapper.find('.oql_history_trigger').length > 0) {
                return;
            }
            
            // Create history trigger button
            var $historyBtn = $('<button class="btn btn-sm oql_history_trigger" type="button" title="Search History" style="flex-shrink: 0;">' +
                               '<i class="fa fa-history"></i></button>');
            
            $wrapper.append($historyBtn);
            
            // Toggle history dropdown
            $historyBtn.on('click', function (e) {
                e.stopPropagation();
                self._toggleHistoryDropdown($wrapper);
            });
            
            // Close dropdown when clicking outside
            $(document).on('click.oqlHistory', function (e) {
                if (!$wrapper.has(e.target).length && self.$historyDropdown && self.$historyDropdown.is(':visible')) {
                    self._hideHistoryDropdown();
                }
            });
        },
        
        /**
         * Toggle history dropdown visibility
         * @param {jQuery} $container History button container
         * @private
         */
        _toggleHistoryDropdown: function ($container) {
            if (this.$historyDropdown && this.$historyDropdown.is(':visible')) {
                this._hideHistoryDropdown();
            } else {
                this._showHistoryDropdown($container);
            }
        },
        
        /**
         * Show history dropdown below the input box
         * @param {jQuery} $wrapper Wrapper container
         * @private
         */
        _showHistoryDropdown: function ($wrapper) {
            var self = this;
            
            // Hide existing dropdown if any
            this._hideHistoryDropdown();
            
            // Get wrapper width for matching
            var wrapperWidth = $wrapper.outerWidth();
            
            // Create dropdown container
            this.$historyDropdown = $('<div class="dropdown-menu oql_history_dropdown" style="display: block; width: ' + wrapperWidth + 'px; max-height: 400px; overflow-y: auto; position: absolute; top: 100%; left: 0; z-index: 1000;"></div>');
            
            // Render history items
            this._renderHistoryDropdown();
            
            // Append dropdown to wrapper (will be positioned absolutely below)
            $wrapper.append(this.$historyDropdown);
        },
        
        /**
         * Hide history dropdown
         * @private
         */
        _hideHistoryDropdown: function () {
            if (this.$historyDropdown) {
                this.$historyDropdown.remove();
                this.$historyDropdown = null;
            }
        },
        
        /**
         * Render history items in dropdown
         * @private
         */
        _renderHistoryDropdown: function () {
            var self = this;
            
            if (!this.$historyDropdown) {
                return;
            }
            
            this.$historyDropdown.empty();
            
            if (this.oqlHistory.length === 0) {
                this.$historyDropdown.append(
                    $('<div class="dropdown-item text-muted" style="padding: 10px;">No search history</div>')
                );
                return;
            }
            
            // Add clear all button
            var $clearBtn = $('<button class="dropdown-item oql_history_clear" type="button">' +
                             '<i class="fa fa-trash-o"></i> Clear All History</button>');
            $clearBtn.on('click', function () {
                self._clearHistory();
                self._hideHistoryDropdown();
            });
            this.$historyDropdown.append($clearBtn);
            this.$historyDropdown.append('<div class="dropdown-divider"></div>');
            
            // Add history items
            this.oqlHistory.forEach(function (item, index) {
                var $itemContainer = $('<div class="dropdown-item oql_history_item" style="padding: 8px; position: relative;"></div>');
                
                // Create textarea for CodeMirror
                var $textarea = $('<textarea style="width: 100%; min-height: 40px; border: none; background: transparent;"></textarea>');
                $textarea.val(item.query);
                $itemContainer.append($textarea);
                
                // Add delete button
                var $deleteBtn = $('<button class="btn btn-link btn-sm" type="button" style="position: absolute; top: 5px; right: 5px; padding: 2px 5px;">' +
                                  '<i class="fa fa-times"></i></button>');
                $deleteBtn.on('click', function (e) {
                    e.stopPropagation();
                    self._removeFromHistory(index);
                });
                $itemContainer.append($deleteBtn);
                
                this.$historyDropdown.append($itemContainer);
                
                // Initialize CodeMirror for this item
                setTimeout(function () {
                    var cm = CodeMirror.fromTextArea($textarea[0], {
                        mode: 'text/x-oql',
                        lineNumbers: false,
                        readOnly: true,
                        viewportMargin: Infinity
                    });
                    cm.setSize('100%', 'auto');
                    
                    // Make item clickable to select
                    $itemContainer.on('click', function (e) {
                        if (!$(e.target).closest('.btn').length) {
                            // First, set the query in the editor
                            self.oqlEditor.setValue(item.query);
                            // Then trigger search
                            self._doOQLSearch(item.query);
                            self._hideHistoryDropdown();
                        }
                    });
                }, 0);
            }.bind(this));
        },

        /**
         * Execute OQL search
         * @private
         */
        _doOQLSearch: function (query) {
            var self = this;
            
            if (!query || !query.trim()) {
                return;
            }
            
            var model = this.model.config.modelName;
            if (!model) {
                console.error('[OQL] No model found');
                return;
            }
            
            // Add to history before searching
            this._addToHistory(query);
            
            // Call searcho method via RPC
            return ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                model: model,
                method: 'searcho',
                args: [[], query],
                kwargs: {}
            }).then(function (result) {
                // Extract IDs from recordset string like "oql.term(881,)"
                var ids = [];
                if (typeof result === 'string') {
                    var match = result.match(/\(([^)]+)\)/);
                    if (match) {
                        ids = match[1].split(',')
                            .map(function (id) { return parseInt(id.trim()); })
                            .filter(function (id) { return !isNaN(id); });
                    }
                }
                
                var queryObj = self.model.get('query');
                queryObj.domain = [['id', 'in', ids]];
                self.model.trigger("search", queryObj);
            }).catch(function (error) {
                console.error('[OQL] Search error:', error);
            });
        },
        
        /**
         * Get storage key for current user and model
         * @private
         */
        _getStorageKey: function (type) {
            var userId = session.uid || 'anonymous';
            if (type === 'TOGGLE_STATE') {
                // Toggle state only by user
                return STORAGE_KEYS[type] + userId;
            } else {
                // History by user + model
                var model = this.model ? this.model.config.modelName : 'unknown';
                return STORAGE_KEYS[type] + userId + '_' + model;
            }
        },
        
        /**
         * Load toggle state from localStorage
         * @private
         */
        _restoreToggleState: function () {
            try {
                var key = this._getStorageKey('TOGGLE_STATE');
                var saved = localStorage.getItem(key);
                if (saved === 'true') {
                    // Trigger toggle to restore state
                    var $btn = $('.o_oql_toggle_btn').first();
                    if ($btn.length > 0 && !this.oqlEnabled) {
                        $btn.trigger('click');
                    }
                }
            } catch (e) {
                console.warn('[OQL] Failed to restore toggle state:', e);
            }
        },
        
        /**
         * Save toggle state to localStorage
         * @private
         */
        _saveToggleState: function () {
            try {
                var key = this._getStorageKey('TOGGLE_STATE');
                localStorage.setItem(key, this.oqlEnabled.toString());
            } catch (e) {
                console.warn('[OQL] Failed to save toggle state:', e);
            }
        },
        
        /**
         * Load history from localStorage
         * @private
         */
        _loadHistory: function () {
            try {
                var key = this._getStorageKey('HISTORY');
                var saved = localStorage.getItem(key);
                return saved ? JSON.parse(saved) : [];
            } catch (e) {
                console.warn('[OQL] Failed to load history:', e);
                return [];
            }
        },
        
        /**
         * Save history to localStorage
         * @private
         */
        _saveHistory: function () {
            try {
                var key = this._getStorageKey('HISTORY');
                localStorage.setItem(key, JSON.stringify(this.oqlHistory));
            } catch (e) {
                console.warn('[OQL] Failed to save history:', e);
            }
        },
        
        /**
         * Add query to history
         * @param {string} query OQL query
         * @private
         */
        _addToHistory: function (query) {
            if (!query || !query.trim()) return;
            
            // Remove duplicate if exists
            this.oqlHistory = this.oqlHistory.filter(function (item) {
                return item.query !== query;
            });
            
            // Add to beginning
            this.oqlHistory.unshift({
                query: query,
                timestamp: Date.now()
            });
            
            // Limit size
            if (this.oqlHistory.length > MAX_HISTORY) {
                this.oqlHistory = this.oqlHistory.slice(0, MAX_HISTORY);
            }
            
            // Save
            this._saveHistory();
            
            // Update dropdown if visible
            if (this.$historyDropdown && this.$historyDropdown.is(':visible')) {
                this._renderHistoryDropdown();
            }
        },
        
        /**
         * Remove item from history
         * @param {number} index Item index
         * @private
         */
        _removeFromHistory: function (index) {
            if (index >= 0 && index < this.oqlHistory.length) {
                this.oqlHistory.splice(index, 1);
                this._saveHistory();
                this._renderHistoryDropdown();
            }
        },
        
        /**
         * Clear all history
         * @private
         */
        _clearHistory: function () {
            this.oqlHistory = [];
            this._saveHistory();
        },
    });
});
