/**
 * OQL Workbench Navbar Button
 * Adds an OQL button to Odoo's top navigation bar.
 * Compatible with multiple Odoo versions (14, 15, 16, 17, 18+).
 */
(function() {
    'use strict';

    // Odoo 18+ no longer exposes jQuery as global $.
    // Grab it from window.jQuery which is available in all versions.
    var $ = window.$;
    if (!$) {
        console.warn('[OQL Navbar] jQuery not available, navbar button skipped');
        return;
    }

    var ATTEMPTS = 20;
    var DELAY = 500; // Start with 500ms

    // Known systray selectors across Odoo versions, from most- to least-specific
    var SYSTRAY_SELECTORS = [
        '.o_menu_systray',             // Odoo 14–17 standard
        '.o-mail-NotificationList',   // Odoo 18+ (discuss module)
        '#o_menu_systray',             // Odoo 14–15 (id variant)
        '.o_systray',                  // Odoo 15 (some builds)
        '.o-navbar-systray',           // Odoo 16 EE variant
        'nav.o_main_navbar .navbar-nav', // generic fallback
    ];

    /**
     * Search for the first visible systray container.
     */
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
