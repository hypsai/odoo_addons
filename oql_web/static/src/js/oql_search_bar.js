/**
 * OQL Search Bar - Odoo 15 version using patch()
 */
odoo.define('oql_web.oql_search_bar', function (require) {
    "use strict";

    var SearchBar = require('web.SearchBar');
    var ajax = require('web.ajax');
    var patch = require('web.utils').patch;
    var OQLEditorCore = require('oql_web.oql_editor_core');

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
            
            // Add OQL button to DOM
            this._addOQLButton();
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
            
            // Create OQL Editor Core instance
            this.oqlEditor = new OQLEditorCore({
                container: $container,
                model: model,
                res_id: null,  // Search bar mode doesn't have a record ID
                fieldName: null,  // Search bar mode doesn't have a field name
                readonly: false,
                lineNumbers: false,
                onSearch: function (query) {
                    self._doOQLSearch(query);
                }
            });
            
            // Start the editor
            this.oqlEditor.start().then(function () {
                self.oqlEditor.focus();
            });
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
                
                if (ids.length > 0) {
                    var queryObj = self.model.get('query');
                    queryObj.domain = [['id', 'in', ids]];
                    self.model.trigger("search", queryObj);
                }
            }).catch(function (error) {
                console.error('[OQL] Search error:', error);
            });
        },
    });
});
