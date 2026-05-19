/**
 * OQL Syntax Highlighting - Standalone Module
 * Registers OQL mode for CodeMirror with complete syntax highlighting rules
 * Can be used in any environment (Odoo, standalone pages, etc.)
 */

(function(window) {
    'use strict';

    /**
     * Register OQL mode for CodeMirror with hardcoded highlighting rules
     * Rules are based on oql.lark grammar definition
     */
    function registerOQLMode() {
        // Check if CodeMirror is available
        if (typeof CodeMirror === 'undefined') {
            console.error('[OQL Highlight] CodeMirror not loaded!');
            return false;
        }

        // Avoid re-registering if already registered
        if (CodeMirror.modes.oql) {
            console.log('[OQL Highlight] OQL mode already registered');
            return true;
        }

        // Define the OQL mode with complete syntax rules
        CodeMirror.defineMode('oql', function() {
            return {
                token: function(stream) {
                    // Skip whitespace
                    if (stream.eatSpace()) {
                        return null;
                    }

                    // Keywords (logical operators and literals)
                    if (stream.match(/^\b(and|or|not|is|null|true|false)\b/)) {
                        return 'keyword';
                    }

                    // Multi-word operators with spaces (must come before single-word operators)
                    if (stream.match(/^not\s+like/) || 
                        stream.match(/^not\s+ilike/) || 
                        stream.match(/^not\s+in/)) {
                        return 'operator';
                    }

                    // Multi-character operators (must come before single-char)
                    if (stream.match(/^(!=|<>|<=|>=|=like|=ilike|=\?|child_of|parent_of)/)) {
                        return 'operator';
                    }

                    // Single-word operators (must be word-bounded to avoid matching in identifiers)
                    if (stream.match(/^\b(like|ilike|in)\b/)) {
                        return 'operator';
                    }

                    // Single-character operators
                    if (stream.match(/^[=<>]/)) {
                        return 'operator';
                    }

                    // Unary operators
                    if (stream.match(/^\bsize\b/)) {
                        return 'operator';
                    }

                    // String literals (single or double quotes)
                    if (stream.match(/^'[^']*'|^"[^"]*"/)) {
                        return 'string';
                    }

                    // Float numbers (must come before int)
                    if (stream.match(/^[-+]?\d+\.\d+/)) {
                        return 'number';
                    }

                    // Integer numbers
                    if (stream.match(/^[-+]?\d+/)) {
                        return 'number';
                    }

                    // Field names and identifiers
                    if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
                        return 'variable';
                    }

                    // Brackets and punctuation
                    if (stream.match(/^[\[\](){}.,]/)) {
                        return 'bracket';
                    }

                    // If no pattern matches, advance one character to avoid infinite loop
                    stream.next();
                    return null;
                }
            };
        });

        // Also define MIME type
        CodeMirror.defineMIME('text/x-oql', 'oql');

        console.log('[OQL Highlight] OQL mode registered successfully');
        return true;
    }

    /**
     * Apply custom styles for OQL tokens
     */
    function applyHighlightStyles() {
        // Check if styles already exist
        if (document.getElementById('oql-highlight-styles')) {
            return;
        }

        var styleElement = document.createElement('style');
        styleElement.id = 'oql-highlight-styles';
        styleElement.textContent = [
            /* Keywords */
            '.cm-keyword { color: #667eea; font-weight: bold; }',
            
            /* Operators */
            '.cm-operator { color: #ff9800; font-weight: bold; }',
            
            /* Numbers */
            '.cm-number { color: #4caf50; }',
            
            /* Strings */
            '.cm-string { color: #e91e63; }',
            
            /* Variables (field names) */
            '.cm-variable { color: #2196f3; }',
            
            /* Brackets */
            '.cm-bracket { color: #9e9e9e; }'
        ].join('\n');

        document.head.appendChild(styleElement);
        console.log('[OQL Highlight] Highlight styles applied');
    }

    /**
     * Initialize OQL highlighting (register mode + apply styles)
     */
    function init() {
        registerOQLMode();
        applyHighlightStyles();
    }

    // Auto-initialize when script loads
    if (typeof CodeMirror !== 'undefined') {
        init();
    } else {
        // Wait for CodeMirror to load
        window.addEventListener('load', function() {
            if (typeof CodeMirror !== 'undefined') {
                init();
            }
        });
    }

    // Export to global scope
    window.OQLHighlight = {
        registerOQLMode: registerOQLMode,
        applyHighlightStyles: applyHighlightStyles,
        init: init
    };

})(window);
