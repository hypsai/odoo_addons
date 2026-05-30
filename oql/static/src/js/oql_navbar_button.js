/**
 * OQL Workbench Navbar Button
 * Adds an OQL button to Odoo's top navigation bar.
 * Compatible with Odoo v13–v19.
 *
 * jQuery ($) is guaranteed to be available synchronously:
 *   v13–v17: bundled in web.assets_common / web.assets_backend
 *   v18+:    explicitly listed before this script in web.assets_backend
 */
(function() {
    'use strict';

    var ATTEMPTS = 20;
    var DELAY = 500; // Start with 500ms

    // Known systray selectors across Odoo versions, from most- to least-specific
    var SYSTRAY_SELECTORS = [
        '.o_menu_systray',              // Odoo 14–17 standard
        '.o-mail-NotificationList',    // Odoo 18+ (discuss module)
        '#o_menu_systray',              // Odoo 14–15 (id variant)
        '.o_systray',                   // Odoo 15 (some builds)
        '.o-navbar-systray',            // Odoo 16 EE variant
        'nav.o_main_navbar .navbar-nav', // generic fallback
    ];

    function findSystray() {
        for (var i = 0; i < SYSTRAY_SELECTORS.length; i++) {
            var $el = $(SYSTRAY_SELECTORS[i]);
            if ($el.length > 0 && $el.is(':visible')) {
                return $el.first();
            }
        }
        return $();
    }

    function addNavbarButton() {
        var attempts = 0;

        function tryAdd() {
            attempts++;
            var $systray = findSystray();

            if ($systray.length && $('#oql_workbench_btn').length === 0) {
                var $button = $('<li class="nav-item">' +
                    '<a id="oql_workbench_btn" href="/oql" class="nav-link oql-workbench-btn" title="OQL Workbench" target="_blank">' +
                        '<i class="fa fa-database"></i>' +
                        '<span>OQL</span>' +
                    '</a>' +
                '</li>');

                $systray.prepend($button);
                return;
            }

            if (attempts < ATTEMPTS) {
                setTimeout(tryAdd, DELAY * attempts);
            }
        }

        tryAdd();
    }

    $(document).ready(function() {
        // Skip the workbench page itself so the button doesn't appear inside itself
        if (!document.body.classList.contains('o_oql_workbench')) {
            addNavbarButton();
        }
    });

})();
