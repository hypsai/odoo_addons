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

        // Define the OQL mode with complete syntax rules based on oql.lark
        CodeMirror.defineMode('oql', function() {
            return {
                token: function(stream) {
                    // Skip whitespace
                    if (stream.eatSpace()) {
                        return null;
                    }

                    // String literals (single quotes with escaped single quotes) - check before keywords
                    if (stream.match(/^'(?:[^']|'')*'/)) {
                        return 'string';
                    }

                    // Multi-word operators with spaces (must come before single-word keywords/operators)
                    if (stream.match(/^not\s+like/i) || 
                        stream.match(/^not\s+ilike/i) || 
                        stream.match(/^not\s+in/i)) {
                        return 'operator';
                    }

                    // ORDER BY clause (multi-word keyword)
                    if (stream.match(/^order\s+by/i)) {
                        return 'keyword';
                    }

                    // SQL-like keywords (case-insensitive)
                    if (stream.match(/^\b(from|select|where|limit|offset|order|by|as)\b/i)) {
                        return 'keyword';
                    }

                    // Logical operators and literals
                    if (stream.match(/^\b(and|or|not|is|null|true|false)\b/i)) {
                        return 'keyword';
                    }

                    // Sorting direction keywords
                    if (stream.match(/^\b(asc|desc)\b/i)) {
                        return 'keyword';
                    }

                    // Multi-character operators (must come before single-char)
                    if (stream.match(/^(!=|<>|<=|>=|=like|=ilike|=\?|child_of|parent_of)/i)) {
                        return 'operator';
                    }

                    // Single-word comparison operators
                    if (stream.match(/^\b(like|ilike|in)\b/i)) {
                        return 'operator';
                    }

                    // Single-character operators
                    if (stream.match(/^[=<>]/)) {
                        return 'operator';
                    }

                    // Translate keyword
                    if (stream.match(/^\btranslate\b/i)) {
                        return 'keyword';
                    }

                    // Float numbers (must come before int)
                    if (stream.match(/^[-+]?\d+\.\d+/)) {
                        return 'number';
                    }

                    // Integer numbers
                    if (stream.match(/^[-+]?\d+/)) {
                        return 'number';
                    }

                    // Field names, model names, and identifiers (dot-separated allowed)
                    if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
                        return 'variable';
                    }

                    // Brackets and punctuation
                    if (stream.match(/^[\[\](){}.,*]/)) {
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
            /* Keywords - Deep purple for language keywords */
            '.cm-keyword { color: #7c3aed; font-weight: 600; }',
            
            /* Operators - Bright orange for operators and comparison symbols */
            '.cm-operator { color: #ea580c; font-weight: 600; }',
            
            /* Numbers - Teal for numeric values */
            '.cm-number { color: #0891b2; }',
            
            /* Strings - Rose red for string literals */
            '.cm-string { color: #dc2626; }',
            
            /* Variables (field names) - Blue for identifiers */
            '.cm-variable { color: #2563eb; }',
            
            /* Brackets - Neutral gray for punctuation */
            '.cm-bracket { color: #64748b; }'
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
