/**
 * OQL Workbench - Standalone Application
 * Independent web app that communicates with Odoo via JSON-RPC
 */

(function() {
    'use strict';

    // ==========================================
    // JSON-RPC Client
    // ==========================================
    var JsonRpcClient = {
        /**
         * Call Odoo JSON-RPC endpoint
         */
        call: function(url, params) {
            return $.ajax({
                url: url,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: params || {},
                    id: Math.floor(Math.random() * 1000000)
                }),
                dataType: 'json'
            }).then(function(response) {
                if (response.error) {
                    throw new Error(response.error.data.message || response.error.message);
                }
                return response.result;
            });
        }
    };

    // ==========================================
    // Query Tab Class
    // ==========================================
    var QueryTab = function(workspace, id, options) {
        this.workspace = workspace;
        this.id = id;
        this.name = options.name || 'Query ' + id;
        this.query = options.query || '';
        this.result = options.result || null;
        this.error = options.error || null;
        this.editor = null;
        this.$element = null;
        this.$content = null;
    };

    QueryTab.prototype = {
        render: function() {
            var self = this;
            
            this.$element = $('<div class="oql-tab" data-tab-id="' + this.id + '">' +
                '<span class="oql-tab-name">' + this.name + '</span>' +
                '<span class="oql-tab-close">×</span>' +
            '</div>');

            // Click on tab to switch
            this.$element.on('click', function(e) {
                if (!$(e.target).hasClass('oql-tab-close')) {
                    self.workspace.switchTab(self.id);
                }
            });

            // Click on close button to close tab
            this.$element.find('.oql-tab-close').on('click', function(e) {
                e.stopPropagation();
                self.workspace.closeTab(self.id);
            });

            this.$content = $('<div class="oql-tab-content">' +
                '<div class="oql-editor-container"></div>' +
                '<div class="oql-result-container"></div>' +
            '</div>');

            return {
                $tab: this.$element,
                $content: this.$content
            };
        },

        initEditor: function() {
            var self = this;
            var $container = this.$content.find('.oql-editor-container');
            
            this.editor = CodeMirror($container[0], {
                mode: 'text/x-oql',
                lineNumbers: true,
                viewportMargin: Infinity,
                extraKeys: {
                    'Ctrl-Space': function(cm) {
                        // Trigger hint
                        CodeMirror.showHint(cm, function(cm) {
                            return self.getHints(cm);
                        });
                    }
                }
            });

            this.editor.on('change', function() {
                self.query = self.editor.getValue();
                self.workspace.saveState();
            });

            if (this.query) {
                this.editor.setValue(this.query);
            }

            return Promise.resolve();
        },

        getHints: function(cm) {
            // Simple keyword hints (can be enhanced with server-side hints)
            var cursor = cm.getCursor();
            var token = cm.getTokenAt(cursor);
            var keywords = ['from', 'select', 'where', 'and', 'or', 'in', 'like', 
                           'limit', 'offset', 'order', 'by', 'asc', 'desc'];
            
            var list = keywords.filter(function(kw) {
                return kw.indexOf(token.string.toLowerCase()) === 0;
            });

            return {
                list: list,
                from: CodeMirror.Pos(cursor.line, token.start),
                to: CodeMirror.Pos(cursor.line, token.end)
            };
        },

        execute: function() {
            var self = this;
            var query = this.editor ? this.editor.getValue() : '';
            
            if (!query.trim()) {
                this.showResult(null, 'Please enter a query');
                return Promise.resolve();
            }

            return JsonRpcClient.call('/oql_query', { query: query })
                .then(function(result) {
                    self.result = result;
                    self.showResult(result, null);
                    self.workspace.saveState();
                })
                .catch(function(error) {
                    console.error('Query error:', error);
                    self.showResult(null, error.message || 'Query execution failed');
                });
        },

        showResult: function(data, error) {
            var $container = this.$content.find('.oql-result-container');
            
            if (error) {
                $container.html('<div class="oql-result-error">' + 
                    '<i class="fa fa-exclamation-circle"></i> ' + error + 
                '</div>');
                return;
            }

            if (!data || !data.length) {
                $container.html('<div class="oql-result-empty">No results</div>');
                return;
            }

            try {
                var headers = Object.keys(data[0]);
                var html = '<table class="oql-result-table"><thead><tr>';
                headers.forEach(function(h) {
                    html += '<th>' + h + '</th>';
                });
                html += '</tr></thead><tbody>';

                data.forEach(function(row) {
                    html += '<tr>';
                    headers.forEach(function(h) {
                        var val = row[h];
                        if (val === null || val === undefined) {
                            val = '<span style="color:#999;">NULL</span>';
                        } else if (typeof val === 'object') {
                            val = JSON.stringify(val);
                        }
                        html += '<td>' + val + '</td>';
                    });
                    html += '</tr>';
                });

                html += '</tbody></table>';
                $container.html(html);
            } catch (e) {
                console.error('Error rendering table:', e);
                $container.html('<div class="oql-result-error">Error rendering results: ' + e.message + '</div>');
            }
        },

        destroy: function() {
            if (this.editor) {
                // CodeMirror instance created on div, use wrapper removal
                var wrapper = this.editor.getWrapperElement();
                if (wrapper && wrapper.parentNode) {
                    wrapper.parentNode.removeChild(wrapper);
                }
                this.editor = null;
            }
        }
    };

    // ==========================================
    // Main Workbench Application
    // ==========================================
    var OQLWorkbench = function() {
        this.tabs = [];
        this.activeTabId = null;
        this.tabCounter = 0;
        this.models = [];
    };

    OQLWorkbench.prototype = {
        start: function() {
            var self = this;
            
            this.renderLayout();
            this.bindEvents();
            
            return this.loadModels().then(function() {
                // Try to load saved state first
                self.loadState();
                
                // If no tabs were loaded, create a default one
                if (self.tabs.length === 0) {
                    self.addTab();
                }
            });
        },

        loadModels: function() {
            var self = this;
            return JsonRpcClient.call('/oql/models', {})
                .then(function(response) {
                    if (response.success) {
                        self.models = response.models;
                        self.renderModelList();
                    }
                })
                .catch(function() {
                    console.warn('Failed to load models');
                    self.models = [];
                });
        },

        renderLayout: function() {
            $('#app').html(
                '<div class="oql-workbench-header">' +
                    '<button class="oql-toolbar-btn btn-primary" id="btn-execute">' +
                        '<i class="fa fa-play"></i> Execute' +
                    '</button>' +
                    '<div class="oql-toolbar-separator"></div>' +
                    '<button class="oql-toolbar-btn" id="btn-new-tab">' +
                        '<i class="fa fa-plus"></i> New Tab' +
                    '</button>' +
                    '<button class="oql-toolbar-btn" id="btn-clear">' +
                        '<i class="fa fa-trash"></i> Clear' +
                    '</button>' +
                '</div>' +
                '<div class="oql-workbench-content">' +
                    '<div class="oql-sidebar">' +
                        '<div class="oql-sidebar-header">Models</div>' +
                        '<div class="oql-model-search">' +
                            '<input type="text" placeholder="Search models..." id="model-search"/>' +
                        '</div>' +
                        '<div class="oql-model-list" id="model-list"></div>' +
                    '</div>' +
                    '<div class="oql-main-area">' +
                        '<div class="oql-tab-bar" id="tab-bar">' +
                            '<div class="oql-tab-add" id="tab-add">+</div>' +
                        '</div>' +
                        '<div class="oql-tabs-content" id="tabs-content"></div>' +
                    '</div>' +
                '</div>' +
                '<div class="oql-status-bar">' +
                    '<div class="oql-status-info">' +
                        '<span id="status-rows">Rows: 0</span>' +
                        '<span id="status-time">Time: 0ms</span>' +
                    '</div>' +
                    '<div>OQL Workspace v1.0</div>' +
                '</div>'
            );
        },

        renderModelList: function(filter) {
            var self = this;
            filter = filter || '';
            
            var html = '';
            this.models.forEach(function(model) {
                if (filter && model.indexOf(filter) === -1) {
                    return;
                }
                html += '<div class="oql-model-item" data-model="' + model + '">' + model + '</div>';
            });
            
            $('#model-list').html(html);
            
            // Double click to open new tab with query
            $('#model-list').find('.oql-model-item').on('dblclick', function() {
                var model = $(this).data('model');
                self.openNewTabWithModel(model);
            });
        },

        bindEvents: function() {
            var self = this;

            $('#btn-execute').on('click', function() {
                self.executeCurrentTab();
            });

            $('#btn-new-tab, #tab-add').on('click', function() {
                self.addTab();
            });

            $('#btn-clear').on('click', function() {
                var tab = self.getActiveTab();
                if (tab && tab.editor) {
                    tab.editor.setValue('');
                }
            });

            $('#model-search').on('input', function() {
                self.renderModelList($(this).val());
            });

            $(document).on('keydown', function(e) {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    self.executeCurrentTab();
                }
                if (e.ctrlKey && e.key === 't') {
                    e.preventDefault();
                    self.addTab();
                }
            });
        },

        addTab: function(options) {
            var self = this;
            this.tabCounter++;
            
            var tab = new QueryTab(this, this.tabCounter, options || {});
            var rendered = tab.render();
            
            this.tabs.push(tab);
            $('#tab-add').before(rendered.$tab);
            $('#tabs-content').append(rendered.$content);
            
            tab.initEditor().then(function() {
                self.switchTab(tab.id);
                self.saveState();
            });
        },

        switchTab: function(tabId) {
            var self = this;
            
            $('.oql-tab').removeClass('active');
            $('.oql-tab-content').removeClass('active');
            
            var tab = this.getTabById(tabId);
            if (tab) {
                tab.$element.addClass('active');
                tab.$content.addClass('active');
                this.activeTabId = tabId;
                
                if (tab.editor) {
                    setTimeout(function() {
                        tab.editor.focus();
                    }, 100);
                }
            }
        },

        closeTab: function(tabId) {
            var index = this.tabs.findIndex(function(t) { return t.id === tabId; });
            
            if (index === -1) return;
            
            var tab = this.tabs[index];
            tab.destroy();
            tab.$element.remove();
            tab.$content.remove();
            this.tabs.splice(index, 1);
            
            if (this.activeTabId === tabId) {
                if (this.tabs.length > 0) {
                    var newIndex = Math.min(index, this.tabs.length - 1);
                    this.switchTab(this.tabs[newIndex].id);
                } else {
                    this.activeTabId = null;
                }
            }
            
            this.saveState();
        },

        getActiveTab: function() {
            return this.getTabById(this.activeTabId);
        },

        getTabById: function(tabId) {
            return this.tabs.find(function(t) { return t.id === tabId; });
        },

        executeCurrentTab: function() {
            var tab = this.getActiveTab();
            if (tab) {
                var startTime = Date.now();
                tab.execute().then(function() {
                    var elapsed = Date.now() - startTime;
                    var rowCount = tab.result ? tab.result.length : 0;
                    $('#status-rows').text('Rows: ' + rowCount);
                    $('#status-time').text('Time: ' + elapsed + 'ms');
                });
            }
        },

        openNewTabWithModel: function(model) {
            var query = 'from ' + model + ' select *';
            this.addTab({ name: model, query: query });
        },

        saveState: function() {
            var state = {
                tabs: this.tabs.map(function(tab) {
                    return {
                        name: tab.name,
                        query: tab.query,
                        result: tab.result
                    };
                }),
                activeTabId: this.activeTabId
            };
            
            localStorage.setItem('oql_workbench_state', JSON.stringify(state));
        },

        loadState: function() {
            var self = this;
            var saved = localStorage.getItem('oql_workbench_state');
            
            if (saved) {
                try {
                    var state = JSON.parse(saved);
                    
                    if (state.tabs && state.tabs.length > 0) {
                        state.tabs.forEach(function(tabData) {
                            self.addTab(tabData);
                        });
                        
                        if (state.activeTabId) {
                            setTimeout(function() {
                                self.switchTab(state.activeTabId);
                            }, 200);
                        }
                    }
                } catch (e) {
                    console.error('Failed to load workspace state:', e);
                }
            }
        }
    };

    // ==========================================
    // Initialize Application
    // ==========================================
    $(document).ready(function() {
        var workbench = new OQLWorkbench();
        workbench.start();
        
        window.oqlWorkbench = workbench;
    });

})();
