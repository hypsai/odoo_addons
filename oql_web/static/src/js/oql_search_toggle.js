/**
 * OQL Search Toggle - Minimal version for Odoo 15
 */
odoo.define('oql_web.oql_search_toggle', function (require) {
    "use strict";

    var ajax = require('web.ajax');

    console.log('[OQL] Module loaded');

    // Try multiple times with increasing delays
    function trySetup(attempt) {
        if (window.__oql_done) return;
        
        var $searchBox = $('.o_searchview_input_container');
        
        if ($searchBox.length > 0) {
            console.log('[OQL] Search box found on attempt', attempt);
            setupToggle($searchBox);
            window.__oql_done = true;
        } else {
            console.log('[OQL] Attempt', attempt, '- No search box, retrying...');
            if (attempt < 20) {
                setTimeout(function() {
                    trySetup(attempt + 1);
                }, 500);
            }
        }
    }

    // Start trying after DOM ready
    $(document).ready(function() {
        console.log('[OQL] Document ready, starting setup attempts');
        setTimeout(function() {
            trySetup(1);
        }, 1000);
    });

    function setupToggle($searchBox) {
        if (window.__oql_done) return;
        window.__oql_done = true;

        var $searchBox = $('.o_searchview_input_container');
        if ($searchBox.length === 0) {
            console.log('[OQL] No search box found');
            return;
        }

        console.log('[OQL] Setting up toggle button');

        // Get the search view container
        var $searchView = $searchBox.closest('.o_searchview');
        if ($searchView.length === 0) {
            $searchView = $searchBox.parent();
        }
        
        // Get the parent of search view and make it flex (not inline-flex)
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

        var useOQL = false;
        var editor = null;

        $btn.on('click', function() {
            useOQL = !useOQL;

            if (useOQL) {
                // Switch to OQL mode
                $btn.addClass('active');
                // Hide only the input field, not the whole container
                $searchBox.find('input, .o_searchview_input').hide();
                $editorDiv.show();

                if (!editor) {
                    createEditor($editorDiv);
                }
            } else {
                // Switch back to normal search
                $btn.removeClass('active');
                // Show the input field again
                $searchBox.find('input, .o_searchview_input').show();
                $editorDiv.hide();

                if (editor) {
                    editor.toTextArea();
                    editor = null;
                    $editorDiv.empty();
                }
            }
        });

        function createEditor($container) {
            if (typeof CodeMirror === 'undefined') {
                console.error('[OQL] CodeMirror not loaded!');
                return;
            }

            $container.empty();
            var $ta = $('<textarea placeholder="Enter OQL query..." style="width:100%;min-height:38px;"></textarea>');
            $container.append($ta);

            setTimeout(function() {
                editor = CodeMirror.fromTextArea($ta[0], {
                    mode: 'text/x-oql',
                    lineNumbers: false,
                    viewportMargin: Infinity,
                    extraKeys: {
                        "Enter": function(cm) {
                            doSearch(cm.getValue());
                        }
                    }
                });
                
                // Force refresh and set size
                setTimeout(function() {
                    editor.refresh();
                    editor.setSize('100%', 'auto');
                    console.log('[OQL] Editor size set to 100%');
                }, 50);
                
                editor.focus();
                console.log('[OQL] Editor ready');
            }, 100);
        }

        function doSearch(query) {
            if (!query || !query.trim()) return;

            // Try multiple ways to get the current model
            var model = null;
            
            // Method 1: From action manager (Odoo 14+)
            if (window.action_manager_current_action && window.action_manager_current_action.res_model) {
                model = window.action_manager_current_action.res_model;
            }
            
            // Method 2: From list view data attribute
            if (!model) {
                var $listView = $('.o_list_view');
                if ($listView.length > 0) {
                    model = $listView.data('model');
                }
            }
            
            // Method 3: From form view data attribute
            if (!model) {
                var $formView = $('.o_form_view');
                if ($formView.length > 0) {
                    model = $formView.data('model');
                }
            }
            
            // Method 4: From URL hash parameters (Odoo uses hash URLs)
            if (!model) {
                var hash = window.location.hash;  // #cids=1&menu_id=4&action=87&model=oql.term...
                if (hash && hash.startsWith('#')) {
                    // Remove the # and parse parameters
                    var hashContent = hash.substring(1);  // cids=1&menu_id=4&action=87&model=oql.term...
                    var hashParams = new URLSearchParams(hashContent);
                    model = hashParams.get('model');
                    console.log('[OQL] Debug - URL hash:', hash);
                    console.log('[OQL] Debug - hash content:', hashContent);
                    console.log('[OQL] Debug - model from hash:', model);
                }
            }
            
            // Method 5: From URL search parameters
            if (!model) {
                var urlParams = new URLSearchParams(window.location.search);
                model = urlParams.get('model') || urlParams.get('res_model');
            }
            
            // Method 5: From body data attribute
            if (!model) {
                model = $('body').data('model');
            }

            console.log('[OQL] Detected model:', model);

            if (!model) {
                console.error('[OQL] No model found');
                console.log('[OQL] Debug - action_manager:', window.action_manager_current_action);
                console.log('[OQL] Debug - list view:', $('.o_list_view').data('model'));
                console.log('[OQL] Debug - URL:', window.location.href);
                alert('Cannot determine current model. Please try from a list view.');
                return;
            }

            console.log('[OQL] Searching:', query, 'on model:', model);

            // Use jQuery ajax directly for better control
            console.log('[OQL] Calling searcho via $.ajax...');
            
            // Add timeout to prevent hanging
            var requestTimeout = setTimeout(function() {
                console.error('[OQL] Request timeout after 10 seconds');
                alert('OQL Error: Request timeout. Please check:\n1. OQL module is installed\n2. searcho method exists\n3. Server is running');
            }, 10000);
            
            // Prepare the RPC payload - correct format for call_kw
            var payload = {
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    model: model,
                    method: 'searcho',
                    args: [[], query],  // First arg is ids (empty list), second is oql_where
                    kwargs: {}
                },
                id: Math.round(Math.random() * 1000)
            };
            
            console.log('[OQL] Payload:', JSON.stringify(payload));
            
            // Make the AJAX call
            $.ajax({
                url: '/web/dataset/call_kw',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(payload),
                dataType: 'json',
                timeout: 10000
            }).done(function(response) {
                clearTimeout(requestTimeout);
                console.log('[OQL] Response:', response);
                
                if (response.error) {
                    console.error('[OQL] Server error:', response.error);
                    alert('OQL Error: ' + (response.error.data?.message || response.error.message || 'Server error'));
                    return;
                }
                
                var result = response.result;
                console.log('[OQL] Success! Result:', result);
                console.log('[OQL] Result type:', typeof result);
                console.log('[OQL] Result string:', String(result));
                
                // searcho returns a recordset, not a domain
                // We need to extract the IDs and create a domain
                if (result) {
                    // Check if result is a recordset string like "oql.term(881,)"
                    var resultStr = String(result);
                    console.log('[OQL] Checking for recordset pattern in:', resultStr);
                    
                    var recordsetMatch = resultStr.match(/\(([^)]+)\)/);
                    console.log('[OQL] Recordset match:', recordsetMatch);
                    
                    if (recordsetMatch) {
                        // Extract IDs from recordset
                        var idsStr = recordsetMatch[1];
                        console.log('[OQL] IDs string:', idsStr);
                        
                        var ids = idsStr.split(',').map(function(id) {
                            return parseInt(id.trim());
                        }).filter(function(id) {
                            return !isNaN(id);
                        });
                        
                        console.log('[OQL] Extracted IDs:', ids);
                        
                        if (ids.length > 0) {
                            // Create domain with 'in' operator
                            var domain = [['id', 'in', ids]];
                            console.log('[OQL] Created domain:', domain);
                            
                            // Apply the domain to the current view using Odoo's internal API
                            // Try to find the control panel and apply filter
                            var $controlPanel = $('.o_control_panel');
                            if ($controlPanel.length > 0) {
                                console.log('[OQL] Found control panel, applying domain...');
                                
                                // Simple approach: reload with domain in hash
                                var currentHash = window.location.hash;
                                var newHash = currentHash.split('&domain=')[0]; // Remove old domain
                                newHash += '&domain=' + encodeURIComponent(JSON.stringify(domain));
                                
                                console.log('[OQL] New hash:', newHash);
                                window.location.hash = newHash;
                                
                                // Force reload to apply the domain
                                setTimeout(function() {
                                    window.location.reload();
                                }, 100);
                            } else {
                                // Fallback: just show alert with results
                                alert('Found ' + ids.length + ' record(s). IDs: ' + ids.join(', '));
                            }
                        } else {
                            alert('No records found matching your query');
                        }
                    } else {
                        console.warn('[OQL] Unexpected result format:', result);
                        console.warn('[OQL] Result type:', typeof result);
                        console.warn('[OQL] Is array?', Array.isArray(result));
                        if (Array.isArray(result)) {
                            console.warn('[OQL] Array length:', result.length);
                            console.warn('[OQL] First few items:', result.slice(0, 3));
                        }
                        alert('Search completed but result format is unexpected. Check console for details.');
                    }
                } else {
                    console.warn('[OQL] No result returned');
                    alert('Search completed but no results found');
                }
            }).fail(function(jqXHR, textStatus, errorThrown) {
                clearTimeout(requestTimeout);
                console.error('[OQL] AJAX failed:', textStatus, errorThrown);
                console.error('[OQL] Response:', jqXHR.responseText);
                alert('OQL Error: ' + (errorThrown || textStatus || 'Request failed'));
            });
        }
    }
});
