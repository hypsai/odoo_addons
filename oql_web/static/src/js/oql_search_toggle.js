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

        // Add button on the left
        var $btn = $('<button class="btn btn-sm o_oql_toggle_btn" type="button" style="margin-right:5px;">' +
                     '<i class="fa fa-code"></i> OQL</button>');
        $searchBox.before($btn);

        // Add editor container
        var $editorDiv = $('<div class="o_oql_editor_container" style="display:none;flex:1;margin-left:5px;"></div>');
        $searchBox.after($editorDiv);

        var useOQL = false;
        var editor = null;

        $btn.on('click', function() {
            useOQL = !useOQL;

            if (useOQL) {
                $btn.addClass('active');
                $searchBox.hide();
                $editorDiv.show();

                if (!editor) {
                    createEditor($editorDiv);
                }
            } else {
                $btn.removeClass('active');
                $searchBox.show();
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
                    extraKeys: {
                        "Enter": function(cm) {
                            doSearch(cm.getValue());
                        }
                    }
                });
                editor.refresh();
                editor.focus();
                console.log('[OQL] Editor ready');
            }, 100);
        }

        function doSearch(query) {
            if (!query || !query.trim()) return;

            var action = window.action_manager_current_action;
            var model = action ? action.res_model : null;

            if (!model) {
                console.error('[OQL] No model');
                alert('Cannot determine current model');
                return;
            }

            console.log('[OQL] Searching:', query);

            ajax.rpc('/web/dataset/call_kw', {
                model: model,
                method: 'searcho',
                args: [query],
                kwargs: {}
            }).done(function(result) {
                console.log('[OQL] Result:', result);
                if (result && result.domain) {
                    window.location.reload();
                }
            }).fail(function(err) {
                console.error('[OQL] Error:', err);
                alert('OQL Error: ' + (err.data?.message || 'Invalid query'));
            });
        }
    }
});
