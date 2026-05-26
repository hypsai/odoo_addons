/**
 * OQL Workbench - Standalone Application
 * Pure frontend SPA communicating with Odoo via JSON-RPC.
 * State is persisted in localStorage only (no server-side dependency).
 */

(function() {
    'use strict';

    // ==========================================
    // JSON-RPC Client
    // ==========================================
    var JsonRpcClient = {
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
                dataType: 'json',
                xhrFields: {
                    withCredentials: true
                }
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
                '<span class="oql-tab-edit-icon" title="Rename tab">&#9998;</span>' +
                '<span class="oql-tab-name">' + this.name + '</span>' +
                '<span class="oql-tab-close">×</span>' +
            '</div>');

            // Click on tab to switch
            this.$element.on('click', function(e) {
                if (!$(e.target).hasClass('oql-tab-close') && !$(e.target).hasClass('oql-tab-edit-icon')) {
                    self.workspace.switchTab(self.id);
                }
            });
            
            // Double-click on tab name to edit
            this.$element.find('.oql-tab-name').on('dblclick', function(e) {
                e.preventDefault();
                e.stopPropagation();
                self.startEditing();
            });
            
            // Click on pencil icon to edit
            this.$element.find('.oql-tab-edit-icon').on('click', function(e) {
                e.stopPropagation();
                self.startEditing();
            });

            // Click on close button to close tab
            this.$element.find('.oql-tab-close').on('click', function(e) {
                e.stopPropagation();
                self.workspace.closeTab(self.id);
            });

            this.$content = $('<div class="oql-tab-content">' +
                '<div class="oql-editor-toolbar">' +
                    '<div class="oql-toolbar-left">' +
                        '<button class="oql-btn-execute" title="Execute (Ctrl+Enter)">' +
                            '<span class="oql-btn-icon">▶</span>' +
                            '<span class="oql-btn-text">Run</span>' +
                        '</button>' +
                        '<button class="oql-btn-stop" title="Stop" style="display:none;">' +
                            '<span class="oql-btn-icon">⏹</span>' +
                            '<span class="oql-btn-text">Stop</span>' +
                            '<span class="oql-loading-spinner"></span>' +
                        '</button>' +
                    '</div>' +
                    '<div class="oql-toolbar-right">' +
                        '<span class="oql-result-info"></span>' +
                    '</div>' +
                '</div>' +
                '<div class="oql-editor-container"></div>' +
                '<div class="oql-result-container"></div>' +
            '</div>');
            
            // Bind execute button
            this.$content.find('.oql-btn-execute').on('click', function() {
                self.execute();
            });
            
            // Bind stop button
            this.$content.find('.oql-btn-stop').on('click', function() {
                self.stopExecution();
            });

            return {
                $tab: this.$element,
                $content: this.$content
            };
        },

        initEditor: function() {
            var self = this;
            var $container = this.$content.find('.oql-editor-container');
            
            if (!window.OQLEditorCore) {
                throw new Error('[OQL Workbench] OQLEditorCore is not loaded.');
            }
            
            this.editorInstance = new window.OQLEditorCore({
                container: $container,
                model: 'base',
                lineNumbers: true,
                readonly: false
            });
            
            return this.editorInstance.start().then(function() {
                self.editor = self.editorInstance.editor;
                
                if (!self.editor || typeof self.editor.refresh !== 'function') {
                    console.error('[OQL] Editor initialization failed');
                    throw new Error('Editor initialization failed');
                }
                
                if (self.query) {
                    self.editor.setValue(self.query);
                }
                
                setTimeout(function() {
                    if (self.editor && typeof self.editor.refresh === 'function') {
                        try {
                            self.editor.refresh();
                            self.editor.focus();
                        } catch (e) {
                            console.error('[OQL] Error during editor refresh:', e);
                        }
                    }
                }, 100);
                
                self.editor.on('change', function() {
                    self.query = self.editor.getValue();
                    self.workspace.saveState();
                });
            }).catch(function(error) {
                console.error('[OQL Workbench] Failed to initialize editor:', error);
                throw error;
            });
        },

        execute: function() {
            var self = this;
            var query = this.editor ? this.editor.getValue() : '';
            
            if (!query.trim()) {
                this.showResult(null, 'Please enter a query');
                return Promise.resolve();
            }
            
            this.setLoading(true);
            
            return new Promise(function(resolve) {
                setTimeout(function() {
                    var xhr = $.ajax({
                        url: '/oql/query',
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify({
                            jsonrpc: '2.0',
                            method: 'call',
                            params: { query: query },
                            id: Math.floor(Math.random() * 1000000)
                        }),
                        dataType: 'json',
                        xhrFields: {
                            withCredentials: true
                        }
                    });
                    
                    self.currentXhr = xhr;
                    
                    xhr.then(function(response) {
                        if (response.error) {
                            throw new Error(response.error.data.message || response.error.message);
                        }
                        var result = response.result;
                        self.result = result;
                        self.showResult(result, null);
                        self.updateResultInfo(result);
                        self.workspace.saveState();
                        self.setLoading(false);
                        self.currentXhr = null;
                        resolve(result);
                    })
                    .catch(function(error) {
                        if (error.statusText !== 'abort' && error.readyState !== 0) {
                            self.showResult(null, error.message || 'Query execution failed');
                        }
                        self.setLoading(false);
                        self.currentXhr = null;
                        resolve(null);
                    });
                }, 0);
            });
        },
        
        setLoading: function(isLoading) {
            var $executeBtn = this.$content.find('.oql-btn-execute');
            var $stopBtn = this.$content.find('.oql-btn-stop');
            var $stopIcon = $stopBtn.find('.oql-btn-icon');
            
            if (isLoading) {
                $executeBtn.hide();
                $stopBtn.css('display', 'flex').addClass('oql-btn-loading');
                $stopIcon.html('⏹');
            } else {
                $executeBtn.show();
                $stopBtn.hide().removeClass('oql-btn-loading');
                $stopIcon.html('⏹');
            }
        },
        
        stopExecution: function() {
            if (this.currentXhr && typeof this.currentXhr.abort === 'function') {
                this.currentXhr.abort();
                this.currentXhr = null;
                this.setLoading(false);
                this.showResult(null, 'Query cancelled by user');
            }
        },
        
        updateResultInfo: function(data) {
            var $info = this.$content.find('.oql-result-info');
            
            if (!data || !data.length) {
                $info.text('');
                return;
            }
            
            var rows = data.length;
            var cols = Object.keys(data[0]).length;
            $info.text(rows + ' rows × ' + cols + ' cols');
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
            if (this.editorInstance) {
                this.editorInstance.destroy();
                this.editorInstance = null;
                this.editor = null;
            }
        },
        
        startEditing: function() {
            var self = this;
            var $nameSpan = this.$element.find('.oql-tab-name');
            var currentName = this.name;
            
            this.isEditing = true;
            
            var $input = $('<input type="text" class="oql-tab-name-input" value="' + currentName + '" />');
            $nameSpan.replaceWith($input);
            
            var focusInput = function() {
                if ($input.length && document.activeElement !== $input[0]) {
                    $input.focus();
                    $input.select();
                }
            };
            
            focusInput();
            setTimeout(focusInput, 50);
            setTimeout(focusInput, 100);
            
            this.$element.find('.oql-tab-edit-icon').hide();
            
            $input.on('mousedown click dblclick', function(e) {
                e.stopPropagation();
            });
            
            var saveEdit = function(newName) {
                newName = newName || $input.val().trim();
                if (newName && newName !== currentName) {
                    self.name = newName;
                    self.workspace.saveState();
                }
                
                $input.replaceWith('<span class="oql-tab-name">' + (newName || currentName) + '</span>');
                self.$element.find('.oql-tab-edit-icon').show();
                
                self.$element.find('.oql-tab-name').on('dblclick', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    self.startEditing();
                });
                
                self.isEditing = false;
            };
            
            $input.on('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    saveEdit();
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    e.stopPropagation();
                    saveEdit(currentName);
                }
            });
            
            var outsideClickHandler = function(e) {
                if (!$(e.target).closest('.oql-tab-name-input').length) {
                    $(document).off('click', outsideClickHandler);
                    saveEdit();
                }
            };
            
            setTimeout(function() {
                $(document).on('click', outsideClickHandler);
            }, 100);
        },
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
            this.loadUserInfo();
            this.initAutoSave();
            
            return this.loadModels().then(function() {
                // Check if localStorage has data
                var localStateStr = localStorage.getItem('oql_workbench_state');
                var hasLocalData = false;
                
                if (localStateStr) {
                    try {
                        var localState = JSON.parse(localStateStr);
                        hasLocalData = localState.tabs && localState.tabs.length > 0;
                    } catch (e) {
                        console.warn('[OQL] Failed to parse local state:', e);
                    }
                }
                
                if (hasLocalData) {
                    // Use localStorage as primary source
                    self.restoreFromLocalStorage();
                } else {
                    // No local data, try to load from cloud (new device / first time)
                    self.syncFromCloud();
                }
                
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
                    '<div class="oql-workbench-title">OQL Workbench</div>' +
                    '<div class="oql-user-info" id="user-info">' +
                        '<i class="fa fa-user"></i> <span>Loading...</span>' +
                    '</div>' +
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
                    '<div>OQL Workbench v1.0</div>' +
                '</div>'
            );
            
            var self = this;
            $('#tab-add').on('click', function() {
                self.addTab();
            });
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
            
            $('#model-list').find('.oql-model-item').on('dblclick', function() {
                var model = $(this).data('model');
                self.openNewTabWithModel(model);
            });
        },

        bindEvents: function() {
            var self = this;

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

            $('#model-search').on('input', function() {
                self.renderModelList($(this).val());
            });
        },
        
        loadUserInfo: function() {
            var self = this;
            JsonRpcClient.call('/oql/user', {})
                .then(function(response) {
                    if (response.success && response.user) {
                        $('#user-info span').text(response.user.name);
                    }
                })
                .catch(function() {
                    $('#user-info span').text('Unknown');
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
            $('.oql-tab').removeClass('active');
            $('.oql-tab-content').removeClass('active');
            
            var tab = this.getTabById(tabId);
            if (tab) {
                tab.$element.addClass('active');
                tab.$content.addClass('active');
                this.activeTabId = tabId;
                
                if (tab.editor && typeof tab.editor.refresh === 'function') {
                    setTimeout(function() {
                        try {
                            tab.editor.refresh();
                            tab.editor.focus();
                        } catch (e) {
                            console.error('[OQL] Error refreshing editor:', e);
                        }
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
            
            setTimeout(function() {
                this.saveState();
            }.bind(this), 0);
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
            var query = 'from ' + model + '\nselect id\nwhere id > 0\nlimit 20';
            this.addTab({ name: model, query: query });
        },

        saveState: function() {
            var state = {
                tabs: this.tabs.map(function(tab) {
                    return {
                        name: tab.name,
                        query: tab.query,
                        active: tab.id === this.activeTabId
                    };
                }, this),
                lastModified: Date.now()
            };
            
            // Save to localStorage immediately (fast, synchronous) - HIGH FREQUENCY
            localStorage.setItem('oql_workbench_state', JSON.stringify(state));
            
            // Trigger async sync to cloud - LOW FREQUENCY (debounced)
            this.triggerCloudSync(state);
        },
        
        initAutoSave: function() {
            var self = this;
            
            this.cloudSyncTimer = null;
            this.cloudSyncDelay = 10000;      // 10 seconds debounce
            this.lastCloudSyncTime = 0;
            this.minCloudSyncInterval = 30000; // Minimum 30 seconds between cloud syncs
            
            // Listen for page unload to sync to cloud immediately
            $(window).on('beforeunload', function() {
                self.syncToCloudImmediately();
            });
        },
        
        triggerCloudSync: function(state) {
            var self = this;
            var now = Date.now();
            
            if (this.cloudSyncTimer) {
                clearTimeout(this.cloudSyncTimer);
            }
            
            var timeSinceLastSync = now - this.lastCloudSyncTime;
            if (timeSinceLastSync < this.minCloudSyncInterval) {
                var remainingWait = this.minCloudSyncInterval - timeSinceLastSync;
                this.cloudSyncTimer = setTimeout(function() {
                    self.syncToCloud(state);
                }, Math.max(remainingWait, this.cloudSyncDelay));
            } else {
                this.cloudSyncTimer = setTimeout(function() {
                    self.syncToCloud(state);
                }, this.cloudSyncDelay);
            }
        },
        
        syncToCloud: function(state) {
            var self = this;
            
            JsonRpcClient.call('/oql/state/save', { state: state })
                .then(function() {
                    self.lastCloudSyncTime = Date.now();
                })
                .catch(function(error) {
                    // Silent fail - auto-save is best-effort
                    console.warn('[OQL] Cloud sync failed:', error.message);
                });
        },
        
        syncToCloudImmediately: function() {
            var state = {
                tabs: this.tabs.map(function(tab) {
                    return { name: tab.name, query: tab.query, active: tab.id === this.activeTabId };
                }, this),
            };
            
            // Synchronous save to localStorage first
            localStorage.setItem('oql_workbench_state', JSON.stringify(state));
            
            // Then try synchronous cloud sync
            try {
                $.ajax({
                    url: '/oql/state/save',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        params: { state: state },
                        id: Math.floor(Math.random() * 1000000)
                    }),
                    async: false,
                    dataType: 'json',
                    xhrFields: { withCredentials: true }
                });
            } catch (e) {
                // localStorage is already saved
            }
        },
        
        syncFromCloud: function() {
            var self = this;
            
            JsonRpcClient.call('/oql/state/load', {})
                .then(function(response) {
                    if (response.success && response.state && response.state.tabs && response.state.tabs.length > 0) {
                        // Cloud state overrides empty localStorage
                        // Clear existing tabs first
                        while (self.tabs.length > 0) {
                            var tab = self.tabs[0];
                            tab.destroy();
                            tab.$element.remove();
                            tab.$content.remove();
                            self.tabs.splice(0, 1);
                        }
                        self.activeTabId = null;
                        
                        self.restoreFromCloud(response.state);
                    }
                })
                .catch(function(error) {
                    console.warn('[OQL] Cloud sync skipped:', error.message);
                });
        },
        
        restoreFromCloud: function(state) {
            var self = this;
            
            if (state.tabs && state.tabs.length > 0) {
                var initPromises = [];
                
                state.tabs.forEach(function(tabData) {
                    var promise = new Promise(function(resolve) {
                        var tab = new QueryTab(self, ++self.tabCounter, tabData);
                        tab.activeOnRestore = tabData.active;  // carry the active flag
                        var rendered = tab.render();
                        
                        self.tabs.push(tab);
                        $('#tab-add').before(rendered.$tab);
                        $('#tabs-content').append(rendered.$content);
                        
                        tab.initEditor().then(function() {
                            resolve(tab.id);
                        }).catch(function() {
                            resolve(tab.id);
                        });
                    });
                    
                    initPromises.push(promise);
                });
                
                Promise.all(initPromises).then(function() {
                    // Activate the tab marked as active, or the first one
                    var activeTab = self.tabs.find(function(t) { return t.activeOnRestore; });
                    if (activeTab) {
                        self.switchTab(activeTab.id);
                    } else if (self.tabs.length > 0) {
                        self.switchTab(self.tabs[0].id);
                    }
                });
            }
        },
        
        restoreFromLocalStorage: function() {
            var self = this;
            var saved = localStorage.getItem('oql_workbench_state');
            
            if (saved) {
                try {
                    var state = JSON.parse(saved);
                    
                    if (state.tabs && state.tabs.length > 0) {
                        var initPromises = [];
                        
                        state.tabs.forEach(function(tabData) {
                            var promise = new Promise(function(resolve) {
                                var tab = new QueryTab(self, ++self.tabCounter, tabData);
                                tab.activeOnRestore = tabData.active;
                                var rendered = tab.render();
                                
                                self.tabs.push(tab);
                                $('#tab-add').before(rendered.$tab);
                                $('#tabs-content').append(rendered.$content);
                                
                                tab.initEditor().then(function() {
                                    resolve(tab);
                                }).catch(function() {
                                    resolve(tab);
                                });
                            });
                            
                            initPromises.push(promise);
                        });
                        
                        Promise.all(initPromises).then(function() {
                            var activeTab = self.tabs.find(function(t) { return t.activeOnRestore; });
                            if (activeTab) {
                                self.switchTab(activeTab.id);
                            } else if (self.tabs.length > 0) {
                                self.switchTab(self.tabs[0].id);
                            }
                        });
                    }
                } catch (e) {
                    console.error('[OQL] Failed to restore state:', e);
                }
            }
        },
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
