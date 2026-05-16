/**
 * OQL Workbench Navbar Button
 * Adds OQL button to Odoo's top navigation bar
 * This file is loaded globally in web.assets_backend
 */

(function() {
    'use strict';

    /**
     * Add OQL Workbench button to Odoo's top navigation bar
     */
    function addNavbarButton() {
        setTimeout(function() {
            var $systray = $('.o_menu_systray');
            
            // Only add if not already present
            if ($systray.length > 0 && $('#oql_workbench_btn').length === 0) {
                var $button = $('<li class="nav-item">' +
                    '<a id="oql_workbench_btn" href="/oql" class="nav-link oql-workbench-btn" title="OQL Workbench" target="_blank">' +
                        '<i class="fa fa-database"></i>' +
                        '<span>OQL</span>' +
                    '</a>' +
                '</li>');
                
                $systray.prepend($button);
            }
        }, 1000);
    }

    // Add button when DOM is ready
    $(document).ready(function() {
        // Only add in backend, not in workbench page itself
        if (!document.body.classList.contains('o_oql_workbench')) {
            addNavbarButton();
        }
    });

})();
