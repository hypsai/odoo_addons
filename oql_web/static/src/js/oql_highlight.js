/**
 * OQL Syntax Highlighting - Hardcoded rules based on oql.lark grammar
 */
odoo.define('oql_web.oql_highlight', function (require) {
    "use strict";

    /**
     * Register OQL mode for CodeMirror with hardcoded highlighting rules
     * Rules are based on oql.lark grammar definition
     */
    function registerOQLMode() {
        // Check if CodeMirror is available
        if (typeof CodeMirror === 'undefined') {
            console.error('[OQL Highlight] CodeMirror not loaded!');
            return;
        }

        // Define the OQL mode with hardcoded patterns
        CodeMirror.defineMode('text/x-oql', function () {
            return {
                token: function (stream) {
                    // Skip whitespace
                    if (stream.eatSpace()) {
                        return null;
                    }

                    // Keywords (logical operators and literals)
                    if (stream.match(/^\b(and|or|not|is|null|true|false)\b/)) {
                        return 'oql-keyword';
                    }

                    // Multi-word operators with spaces (must come before single-word operators)
                    if (stream.match(/^not\s+like/) || 
                        stream.match(/^not\s+ilike/) || 
                        stream.match(/^not\s+in/)) {
                        return 'oql-operator';
                    }

                    // Multi-character operators (must come before single-char)
                    if (stream.match(/^(!=|<>|<=|>=|=like|=ilike|=\?|child_of|parent_of)/)) {
                        return 'oql-operator';
                    }

                    // Single-word operators (must be word-bounded to avoid matching in identifiers)
                    if (stream.match(/^\b(like|ilike|in)\b/)) {
                        return 'oql-operator';
                    }

                    // Single-character operators
                    if (stream.match(/^[=<>]/)) {
                        return 'oql-operator';
                    }

                    // Unary operators
                    if (stream.match(/^\bsize\b/)) {
                        return 'oql-operator';
                    }

                    // String literals (single or double quotes)
                    if (stream.match(/^'[^']*'|^"[^"]*"/)) {
                        return 'oql-string';
                    }

                    // Float numbers (must come before int)
                    if (stream.match(/^[-+]?\d+\.\d+/)) {
                        return 'oql-number';
                    }

                    // Integer numbers
                    if (stream.match(/^[-+]?\d+/)) {
                        return 'oql-number';
                    }

                    // Field names and identifiers
                    if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
                        return 'oql-variable';
                    }

                    // Brackets and punctuation
                    if (stream.match(/^[\[\](){}.,]/)) {
                        return 'oql-bracket';
                    }

                    // If no pattern matches, advance one character to avoid infinite loop
                    stream.next();
                    return null;
                }
            };
        });

        // Also define MIME type
        CodeMirror.defineMIME('text/x-oql', 'text/x-oql');
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
            '.cm-oql-keyword { color: #667eea; font-weight: bold; }',
            
            /* Operators */
            '.cm-oql-operator { color: #ff9800; font-weight: bold; }',
            
            /* Numbers */
            '.cm-oql-number { color: #4caf50; }',
            
            /* Strings */
            '.cm-oql-string { color: #e91e63; }',
            
            /* Variables (field names) */
            '.cm-oql-variable { color: #2196f3; }',
            
            /* Brackets */
            '.cm-oql-bracket { color: #9e9e9e; }'
        ].join('\n');

        document.head.appendChild(styleElement);
    }

    // Auto-register when module loads
    registerOQLMode();
    applyHighlightStyles();

    return {
        registerOQLMode: registerOQLMode,
        applyHighlightStyles: applyHighlightStyles
    };
});
