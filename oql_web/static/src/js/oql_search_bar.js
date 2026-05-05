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
        HISTORY: 'oql_search_history_',
        LAST_QUERY: 'oql_last_query_',  // Cache for last OQL query per user+model+view
        CURSOR_POSITION: 'oql_cursor_pos_'  // Cache for cursor position
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
            this.isRestoringQuery = false;  // Flag to prevent saving cursor during restore
            
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
            
            // Create editor container that will REPLACE the native search box
            // Insert it AFTER the entire search view (not inside search box)
            var $editorDiv = $('<div class="o_oql_editor_container" style="display:none;width:100%;position:relative;"></div>');
            $searchView.after($editorDiv);
            
            // Toggle button click handler
            $btn.on('click', function () {
                self._toggleOQL($btn, $searchView, $editorDiv);
            });
        },

        /**
         * Toggle OQL mode on/off
         * @private
         */
        _toggleOQL: function ($btn, $searchView, $editorDiv) {
            var self = this;
            this.oqlEnabled = !this.oqlEnabled;
            
            if (this.oqlEnabled) {
                // Switch to OQL mode - hide entire native search view
                $btn.addClass('active');
                $searchView.hide();
                $editorDiv.show();
                
                if (!this.oqlEditor) {
                    this._initOQLEditor($editorDiv);
                } else {
                    this.oqlEditor.focus();
                }
            } else {
                // Switch back to normal search - show native search view
                $btn.removeClass('active');
                $searchView.show();
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
            var $wrapper = $('<div class="oql_combobox_wrapper" style="position: relative; display: flex; align-items: flex-start; width: 100%;"></div>');
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
                    // Clear error tooltip on blur
                    self._hideErrorTooltip();
                });
                
                // Add change handler to clear error state
                self.oqlEditor.editor.on('change', function () {
                    self._clearErrorState();
                });
                
                // Add cursor activity handler to save cursor position
                self.oqlEditor.editor.on('cursorActivity', function () {
                    self._saveCursorPosition();
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
            
            // Create dropdown container with scrollable area
            this.$historyDropdown = $('<div class="dropdown-menu oql_history_dropdown" style="display: block; width: ' + wrapperWidth + 'px; position: absolute; top: 100%; left: 0; z-index: 1000;"></div>');
            
            // Create scrollable list container
            var $listContainer = $('<div class="oql_history_list" style="max-height: 350px; overflow-y: auto;"></div>');
            this.$historyDropdown.append($listContainer);
            
            // Render history items into the list container
            this._renderHistoryDropdown($listContainer);
            
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
         * @param {jQuery} $listContainer List container for scrollable area
         * @private
         */
        _renderHistoryDropdown: function ($listContainer) {
            var self = this;
            
            if (!this.$historyDropdown || !$listContainer) {
                return;
            }
            
            $listContainer.empty();
            
            if (this.oqlHistory.length === 0) {
                $listContainer.append(
                    $('<div class="dropdown-item text-muted" style="padding: 10px;">No search history</div>')
                );
                // Add clear button outside list even when empty
                this._addClearButtonOutsideList();
                return;
            }
            
            // Add history items to scrollable list
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
                
                $listContainer.append($itemContainer);
                
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
            
            // Add clear button outside the scrollable list
            this._addClearButtonOutsideList();
        },
        
        /**
         * Add clear all button outside the scrollable list
         * @private
         */
        _addClearButtonOutsideList: function () {
            var self = this;
            
            // Add divider
            this.$historyDropdown.append('<div class="dropdown-divider" style="margin: 5px 0;"></div>');
            
            // Add clear all button
            var $clearBtn = $('<button class="dropdown-item oql_history_clear" type="button" style="font-weight: bold;">' +
                             '<i class="fa fa-trash-o"></i> Clear All History</button>');
            $clearBtn.on('click', function () {
                self._clearHistory();
                self._hideHistoryDropdown();
            });
            this.$historyDropdown.append($clearBtn);
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
            
            // Save as last query for restore after page refresh
            this._saveLastQuery(query);
            
            // Call searcho_ids method via RPC
            return ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                model: model,
                method: 'searcho_ids',
                args: [query],
                kwargs: {}
            }).then(function (result) {
                // Extract IDs from recordset string like "oql.term(881,)"
                var ids = result;
                var queryObj = self.model.get('query');
                queryObj.context['active_test'] = false;
                queryObj.domain = [['id', 'in', ids]];
                self.model.trigger("search", queryObj);
            }).catch(function (error) {
                var errorMessage = error?.message?.data?.message || error?.message || 'OQL query error';
                self._showErrorState(errorMessage);
            });
        },
        
        /**
         * Show error state with red border and tooltip
         * @param {string} errorMessage Error message to display
         * @private
         */
        _showErrorState: function (errorMessage) {
            var self = this;
            var $wrapper = $('.oql_combobox_wrapper', this.$el);
            
            if ($wrapper.length === 0) {
                return;
            }
            
            // Add error class for red border
            $wrapper.addClass('oql-error');
            
            // Store error message
            this.oqlErrorMessage = errorMessage;
            
            // Setup hover on CodeMirror editor only (not the whole wrapper)
            var $editor = $wrapper.find('.CodeMirror').first();
            $editor.off('mouseenter.oqlError').on('mouseenter.oqlError', function () {
                if (self.oqlErrorMessage) {
                    // Delay showing tooltip on hover
                    self._hoverTooltipTimeout = setTimeout(function () {
                        self._showErrorTooltip(self.oqlErrorMessage);
                    }, 500);
                }
            });
            
            $editor.off('mouseleave.oqlError').on('mouseleave.oqlError', function () {
                if (self._hoverTooltipTimeout) {
                    clearTimeout(self._hoverTooltipTimeout);
                    self._hoverTooltipTimeout = null;
                }
                self._hideErrorTooltip();
            });
        },
        
        /**
         * Clear error state (remove red border)
         * @private
         */
        _clearErrorState: function () {
            var $wrapper = $('.oql_combobox_wrapper', this.$el);
            
            if ($wrapper.length === 0) {
                return;
            }
            
            // Remove error class
            $wrapper.removeClass('oql-error');
            
            // Clear error message
            this.oqlErrorMessage = null;
            
            // Hide tooltip
            this._hideErrorTooltip();
            
            // Remove hover handlers
            $wrapper.off('mouseenter.oqlError mouseleave.oqlError');
        },
        
        /**
         * Show error tooltip
         * @param {string} message Error message
         * @private
         */
        _showErrorTooltip: function (message) {
            var self = this;
            
            // Hide existing tooltip
            this._hideErrorTooltip();
            
            var $wrapper = $('.oql_combobox_wrapper', this.$el);
            if ($wrapper.length === 0) {
                return;
            }
            
            // Create tooltip element - display below the input
            this.$errorTooltip = $('<div class="oql_error_tooltip" style="position: absolute; top: 100%; left: 0; right: 0; margin-top: 8px; padding: 10px; background-color: #dc3545; color: white; border-radius: 4px; font-size: 12px; z-index: 1001; box-shadow: 0 2px 8px rgba(0,0,0,0.15); animation: oqlTooltipFadeIn 0.2s ease;">' +
                                   '<i class="fa fa-exclamation-circle" style="margin-right: 5px;"></i>' +
                                   _.escape(message) +
                                   '</div>');
            
            $wrapper.append(this.$errorTooltip);
        },
        
        /**
         * Hide error tooltip
         * @private
         */
        _hideErrorTooltip: function () {
            if (this.$errorTooltip) {
                this.$errorTooltip.remove();
                this.$errorTooltip = null;
            }
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
                // History and last query by user + model
                var model = this.model ? this.model.config.modelName : 'unknown';
                return STORAGE_KEYS[type] + userId + '_' + model;
            }
        },
        
        /**
         * Load toggle state from localStorage
         * @private
         */
        _restoreToggleState: function () {
            var self = this;
            try {
                var key = this._getStorageKey('TOGGLE_STATE');
                var saved = localStorage.getItem(key);
                if (saved === 'true') {
                    // Trigger toggle to restore state
                    var $btn = $('.o_oql_toggle_btn').first();
                    if ($btn.length > 0 && !this.oqlEnabled) {
                        $btn.trigger('click');
                        
                        // After toggle is enabled, restore last query and auto-search
                        setTimeout(function() {
                            self._restoreLastQuery();
                        }, 300);  // Wait for editor to initialize
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
                // Find and remove the DOM element directly for smooth UX
                var $listContainer = this.$historyDropdown ? this.$historyDropdown.find('.oql_history_list') : null;
                if ($listContainer && $listContainer.length > 0) {
                    var $items = $listContainer.find('.oql_history_item');
                    if ($items.length > index) {
                        // Animate removal
                        var $itemToRemove = $items.eq(index);
                        $itemToRemove.css({
                            'transition': 'all 0.2s ease',
                            'opacity': '0',
                            'max-height': '0',
                            'padding': '0',
                            'margin': '0'
                        });
                        
                        // Remove after animation
                        setTimeout(function () {
                            $itemToRemove.remove();
                            
                            // Check if list is now empty
                            if ($listContainer.find('.oql_history_item').length === 0) {
                                // Show empty state
                                $listContainer.append(
                                    $('<div class="dropdown-item text-muted" style="padding: 10px;">No search history</div>')
                                );
                            }
                        }, 200);
                    }
                }
                
                // Update data
                this.oqlHistory.splice(index, 1);
                this._saveHistory();
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
        
        /**
         * Save last OQL query to localStorage
         * @param {string} query OQL query
         * @private
         */
        _saveLastQuery: function (query) {
            try {
                if (!query || !query.trim()) {
                    // Clear saved query if empty
                    var key = this._getStorageKey('LAST_QUERY');
                    localStorage.removeItem(key);
                    return;
                }
                
                var key = this._getStorageKey('LAST_QUERY');
                localStorage.setItem(key, query);
            } catch (e) {
                console.warn('[OQL] Failed to save last query:', e);
            }
        },
        
        /**
         * Restore last OQL query and auto-search
         * @private
         */
        _restoreLastQuery: function () {
            var self = this;
            try {
                var key = this._getStorageKey('LAST_QUERY');
                var savedQuery = localStorage.getItem(key);
                
                if (savedQuery && this.oqlEditor) {
                    // Get saved cursor position before setting value
                    var cursorKey = this._getStorageKey('CURSOR_POSITION');
                    var savedPos = localStorage.getItem(cursorKey);
                    var cursor = null;
                    
                    if (savedPos) {
                        try {
                            cursor = JSON.parse(savedPos);
                        } catch (e) {
                            console.warn('[OQL] Failed to parse cursor position:', e);
                        }
                    }
                    
                    // Set the query in editor (this resets cursor to beginning)
                    this.oqlEditor.setValue(savedQuery);
                    
                    // Restore cursor position after setValue
                    setTimeout(function() {
                        if (cursor && self.oqlEditor && self.oqlEditor.editor) {
                            try {
                                var doc = self.oqlEditor.editor.getDoc();
                                var lineCount = doc.lineCount();

                                if (cursor.line >= 0 && cursor.line < lineCount) {
                                    var lineLength = doc.getLine(cursor.line).length;
                                    if (cursor.ch >= 0 && cursor.ch <= lineLength) {
                                        self.oqlEditor.editor.setCursor(cursor);
                                    } else {
                                        console.warn('[OQL] Cursor ch out of range:', cursor.ch, 'vs', lineLength);
                                    }
                                } else {
                                    console.warn('[OQL] Cursor line out of range:', cursor.line, 'vs', lineCount);
                                }
                            } catch (e) {
                                console.error('[OQL] Error restoring cursor:', e);
                            }
                        }
                        
                        // Auto-trigger search after a short delay
                        setTimeout(function() {
                            self._doOQLSearch(savedQuery);
                        }, 100);
                    }, 50);
                }
            } catch (e) {
                console.warn('[OQL] Failed to restore last query:', e);
            }
        },
        
        /**
         * Save cursor position to localStorage
         * @private
         */
        _saveCursorPosition: function () {
            if (!this.oqlEditor || !this.oqlEnabled) return;
            
            try {
                var cursor = this.oqlEditor.editor.getCursor();
                var key = this._getStorageKey('CURSOR_POSITION');
                localStorage.setItem(key, JSON.stringify(cursor));
            } catch (e) {
                console.warn('[OQL] Failed to save cursor position:', e);
            }
        },
        
        /**
         * Restore cursor position from localStorage
         * @private
         */
        _restoreCursorPosition: function () {
            if (!this.oqlEditor) return;
            
            try {
                var key = this._getStorageKey('CURSOR_POSITION');
                var savedPos = localStorage.getItem(key);
                
                if (savedPos) {
                    var cursor = JSON.parse(savedPos);
                    // Validate cursor position
                    var doc = this.oqlEditor.editor.getDoc();
                    var lineCount = doc.lineCount();
                    
                    if (cursor.line >= 0 && cursor.line < lineCount) {
                        var lineLength = doc.getLine(cursor.line).length;
                        if (cursor.ch >= 0 && cursor.ch <= lineLength) {
                            this.oqlEditor.editor.setCursor(cursor);
                        }
                    }
                }
            } catch (e) {
                console.warn('[OQL] Failed to restore cursor position:', e);
            }
        },
    });
});
