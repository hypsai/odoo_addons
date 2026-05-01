/**
 * OQL Search Bar - Odoo 15 version using patch()
 */
odoo.define('oql_web.oql_search_bar', function (require) {
    "use strict";

    var SearchBar = require('web.SearchBar');
    var ajax = require('web.ajax');
    var patch = require('web.utils').patch;

    console.log('[OQL] Loading OQL SearchBar extension...');

    // Extend SearchBar using patch()
    patch(SearchBar.prototype, 'oql_web.SearchBar', {
        /**
         * Initialize OQL state and add button after component is mounted
         */
        mounted: function () {
            this._super.apply(this, arguments);
            
            // Add OQL state
            this.oqlEnabled = false;
            this.oqlCodeMirror = null;
            
            // Add OQL button to DOM
            this._addOQLButton();
            
            console.log('[OQL] SearchBar mounted with OQL support');
        },

        willUnmount: function () {
            this._super.apply(this, arguments);
            
            // Cleanup CodeMirror if exists
            if (this.oqlCodeMirror) {
                this.oqlCodeMirror.toTextArea();
                this.oqlCodeMirror = null;
            }
        },

        /**
         * Add OQL toggle button to the search bar
         * @private
         */
        _addOQLButton: function () {
            var self = this;
            
            // Use jQuery to find elements in the component's DOM
            // this.el might be the input container, so we need to go up to find the searchview
            var $current = $(this.el);
            console.log('[OQL] Current element:', this.el.className);
            
            // Try to find o_searchview from current element or its parents
            var $searchView = $current.closest('.o_searchview');
            if ($searchView.length === 0) {
                $searchView = $current.find('.o_searchview');
            }
            if ($searchView.length === 0) {
                $searchView = $current.siblings('.o_searchview');
            }
            
            var $searchBox = $current.closest('.o_searchview_input_container');
            if ($searchBox.length === 0) {
                $searchBox = $current.find('.o_searchview_input_container');
            }
            
            console.log('[OQL] Found searchView:', $searchView.length, $searchView[0]);
            console.log('[OQL] Found searchBox:', $searchBox.length, $searchBox[0]);
            
            if ($searchView.length === 0) {
                console.warn('[OQL] Search view not found, trying alternative...');
                // Last resort: search from document
                $searchView = $('.o_searchview').first();
                $searchBox = $('.o_searchview_input_container').first();
                console.log('[OQL] Alternative search - searchView:', $searchView.length);
            }
            
            if ($searchView.length === 0) {
                console.error('[OQL] Cannot find search view anywhere');
                return;
            }
            
            // Check if button already exists
            if ($searchView.parent().find('.o_oql_toggle_btn').length > 0) {
                console.log('[OQL] OQL button already exists');
                return;
            }
            
            // Get parent and make it flex
            var $parent = $searchView.parent();
            $parent.css('display', 'flex');
            $parent.css('align-items', 'center');
            $parent.css('flex-wrap', 'nowrap');
            $parent.css('width', '100%');
            
            // Add button BEFORE the search view
            var $btn = $('<button class="btn btn-sm o_oql_toggle_btn" type="button" style="margin-right:5px;flex-shrink:0;">' +
                         '<i class="fa fa-code"></i> OQL</button>');
            $searchView.before($btn);
            
            // Make search view take remaining space
            $searchView.css('flex', '1');
            $searchView.css('min-width', '0');
            
            // Add editor container INSIDE the search box container
            var $editorDiv = $('<div class="o_oql_editor_container" style="display:none;width:100%;"></div>');
            $searchBox.after($editorDiv);
            
            // Toggle button click handler
            $btn.on('click', function () {
                self._toggleOQL($btn, $searchBox, $editorDiv);
            });
            
            console.log('[OQL] OQL button added successfully');
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
                
                if (!this.oqlCodeMirror) {
                    this._initCodeMirror($editorDiv);
                }
            } else {
                // Switch back to normal search
                $btn.removeClass('active');
                $searchBox.show();
                $editorDiv.hide();
                
                if (this.oqlCodeMirror) {
                    this.oqlCodeMirror.toTextArea();
                    this.oqlCodeMirror = null;
                    $editorDiv.empty();
                }
            }
        },

        /**
         * Initialize CodeMirror editor
         * @private
         */
        _initCodeMirror: function ($container) {
            var self = this;
            
            if (typeof CodeMirror === 'undefined') {
                console.error('[OQL] CodeMirror not loaded!');
                return;
            }
            
            $container.empty();
            var $ta = $('<textarea placeholder="Enter OQL query..." style="width:100%;min-height:38px;"></textarea>');
            $container.append($ta);
            
            setTimeout(function () {
                self.oqlCodeMirror = CodeMirror.fromTextArea($ta[0], {
                    mode: 'text/x-oql',
                    lineNumbers: false,
                    viewportMargin: Infinity,
                    extraKeys: {
                        "Enter": function (cm) {
                            self._doOQLSearch(cm.getValue());
                        }
                    }
                });
                
                // Force refresh and set size
                setTimeout(function () {
                    self.oqlCodeMirror.refresh();
                    self.oqlCodeMirror.setSize('100%', 'auto');
                    console.log('[OQL] Editor size set to 100%');
                }, 50);
                
                self.oqlCodeMirror.focus();
                console.log('[OQL] Editor ready');
            }, 100);
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
            
            console.log('[OQL] Searching:', query);
            
            // Get current model from searchModel
            var model = this.model.config.modelName;
            console.log('[OQL] Current model:', model);
            
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
                console.log('[OQL] Result:', result);
                
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
                
                console.log('[OQL] Extracted IDs:', ids);
                
                if (ids.length > 0) {
                    // Create domain
                    var model = self.model;
                    var domain = [['id', 'in', ids]];
                    var queryObj = model.get('query');
                    queryObj.domain = domain;

                    model.trigger("search", queryObj);
                } else {
                    console.log('No records found matching your query');
                }
            }).catch(function (error) {
                console.error('[OQL] Error:', error);
            });
        },
    });

    console.log('[OQL] SearchBar extension complete');
});
