/**
 * OQL Editor Core - Standalone Version
 * Reusable CodeMirror-based OQL editor with intelligent hints
 * Can be used in any environment (Odoo backend, standalone pages, etc.)
 */

(function(window) {
    'use strict';

    // ==========================================
    // Register OQL Mode for CodeMirror
    // ==========================================
    if (typeof CodeMirror !== 'undefined') {
        CodeMirror.defineMode("oql", function(config, parserConfig) {
            var keywords = parserConfig.keywords || {};
            
            function regexClass(src) {
                return new RegExp("^[" + src + "]");
            }
            
            var puncChars = regexClass("\\(\\)\\[\\]\\{\\},:;");
            var operatorChars = regexClass("\\*\\+\\-\\/=<>");
            
            function tokenBase(stream, state) {
                var ch = stream.next();
                
                // Comment
                if (ch == "#") {
                    stream.skipToEnd();
                    return "comment";
                }
                
                // String
                if (ch == "'" || ch == '"') {
                    state.tokenize = tokenString(ch);
                    return state.tokenize(stream, state);
                }
                
                // Number
                if (/\d/.test(ch)) {
                    stream.eatWhile(/[\w\.]/);
                    return "number";
                }
                
                // Operators
                if (operatorChars.test(ch)) {
                    stream.eatWhile(operatorChars);
                    return "operator";
                }
                
                // Punctuation
                if (puncChars.test(ch)) {
                    return null;
                }
                
                // Keywords and identifiers
                stream.eatWhile(/[\w\$_]/);
                var word = stream.current().toLowerCase();
                
                if (keywords.hasOwnProperty(word)) {
                    return "keyword";
                }
                
                return "variable";
            }
            
            function tokenString(quote) {
                return function(stream, state) {
                    var escaped = false, next;
                    while ((next = stream.next()) != null) {
                        if (next == quote && !escaped) break;
                        escaped = !escaped && next == "\\";
                    }
                    if (!escaped) state.tokenize = tokenBase;
                    return "string";
                };
            }
            
            return {
                startState: function() {
                    return {tokenize: tokenBase};
                },
                token: function(stream, state) {
                    if (stream.eatSpace()) return null;
                    return state.tokenize(stream, state);
                }
            };
        });

        CodeMirror.defineMIME("text/x-oql", {
            name: "oql",
            keywords: {
                "from": true, "select": true, "where": true, "and": true, "or": true,
                "in": true, "like": true, "not": true, "null": true, "true": true,
                "false": true, "limit": true, "offset": true, "order": true, "by": true,
                "asc": true, "desc": true, "group": true, "having": true, "count": true,
                "sum": true, "avg": true, "min": true, "max": true, "as": true
            }
        });
    }

    // ==========================================
    // OQL Editor Core Class
    // ==========================================
    var OQLEditorCore = function(options) {
        this.container = options.container;
        this.model = options.model || 'base';
        this.readonly = options.readonly || false;
        this.lineNumbers = options.lineNumbers || false;
        this.onSearch = options.onSearch || null;
        this.onChange = options.onChange || null;
        
        this.editor = null;
        this.$textarea = null;
        this._cachedHintsGroup = {};
    };

    OQLEditorCore.prototype = {
        /**
         * Initialize the CodeMirror editor
         */
        start: function() {
            if (typeof CodeMirror === 'undefined') {
                console.error('[OQL] CodeMirror not loaded!');
                return Promise.reject(new Error('CodeMirror not loaded'));
            }

            var self = this;
            this.$textarea = $('<textarea placeholder="Enter OQL query..." style="width:100%;min-height:38px;"></textarea>');
            this.container.empty().append(this.$textarea);

            return new Promise(function(resolve) {
                requestAnimationFrame(function() {
                    self.editor = CodeMirror.fromTextArea(self.$textarea[0], {
                        mode: 'text/x-oql',
                        lineNumbers: self.lineNumbers,
                        readOnly: self.readonly,
                        viewportMargin: Infinity,
                        extraKeys: self._getExtraKeys()
                    });

                    // Setup event listeners
                    self._setupEventListeners();

                    // Refresh and set size
                    self.editor.refresh();
                    self.editor.setSize('100%', 'auto');
                    
                    resolve();
                });
            });
        },

        /**
         * Get CodeMirror extra keys configuration
         * @private
         */
        _getExtraKeys: function() {
            var self = this;
            var keys = {};

            // Ctrl-Space for manual hint trigger (standard)
            keys["Ctrl-Space"] = function(cm) {
                console.log('[OQL Standalone] Ctrl-Space pressed');
                self._showHint(cm, false);
            };
            
            // Also support just pressing Ctrl (for convenience)
            keys["Ctrl"] = function(cm) {
                console.log('[OQL Standalone] Ctrl pressed');
                self._showHint(cm, false);
            };

            return keys;
        },

        /**
         * Setup event listeners
         * @private
         */
        _setupEventListeners: function() {
            var self = this;
            var hintTimeout = null;

            // Change listener for auto-hints
            this.editor.on('change', function(cm, change) {
                if (change.origin === '+input') {
                    // Notify onChange callback if provided
                    if (self.onChange) {
                        self.onChange(cm.getValue());
                    }
                    
                    // Show hints on any input (PyCharm-style)
                    // Debounce hint display
                    if (hintTimeout) {
                        clearTimeout(hintTimeout);
                    }
                    
                    hintTimeout = setTimeout(function() {
                        self._showHint(cm);
                    }, 150); // Reduced to 150ms for faster response
                }
            });
        },

        /**
         * Get current editor value
         */
        getValue: function() {
            return this.editor ? this.editor.getValue() : '';
        },

        /**
         * Set editor value
         */
        setValue: function(value) {
            if (this.editor) {
                this.editor.setValue(value || '');
            }
        },

        /**
         * Focus the editor
         */
        focus: function() {
            if (this.editor) {
                this.editor.focus();
            }
        },

        /**
         * Destroy the editor instance
         */
        destroy: function() {
            if (this.editor) {
                var wrapper = this.editor.getWrapperElement();
                if (wrapper && wrapper.parentNode) {
                    wrapper.parentNode.removeChild(wrapper);
                }
                this.editor = null;
            }
            this._cachedHintsGroup = {};
        },

        /**
         * Show hints with CodeMirror popup
         * @param {Object} cm CodeMirror instance
         * @param {boolean} [strict=false] Strict matching mode
         * @private
         */
        _showHint: function(cm, strict) {
            if (this.readonly) {
                console.log('[OQL Standalone] Editor is readonly, skip hint');
                return;
            }
            strict = strict || false;
            
            console.log('[OQL Standalone] _showHint called, strict:', strict);
            
            var self = this;
            CodeMirror.showHint(cm, function(cm, callback) {
                console.log('[OQL Standalone] CodeMirror.showHint callback invoked');
                // Use Promise to handle async operation
                self._getHints(cm, strict).then(function(hints) {
                    console.log('[OQL Standalone] Hints resolved, calling callback');
                    callback(hints);
                }).catch(function(error) {
                    console.error('[OQL] Error getting hints:', error);
                    callback({ list: [], from: cm.getCursor(), to: cm.getCursor() });
                });
            }, {
                'completeSingle': false,
                'async': true  // Enable async mode
            });
        },

        /**
         * Get hints from cache or server
         * @param {Object} cm CodeMirror instance
         * @param {boolean} strict Strict matching mode
         * @private
         */
        _getHints: async function(cm, strict) {
            console.log('[OQL Standalone] _getHints called');
            var self = this;
            var cursor = cm.getCursor();
            var doc = cm.getDoc();
            var content = doc.getValue();
            var cursorIndex = doc.indexFromPos(cursor);
            var token = self._getCurrentToken(cm);
            console.log('[OQL Standalone] Token:', token, 'Content length:', content.length);
            
            var prefix = content.substring(0, cursorIndex - token.length);
            var context = prefix.trim();
            var tokenStart = cursorIndex - token.length;
            var from = doc.posFromIndex(tokenStart);
            var to = cursor;
            var limit = 100;

            // Load hints from cache
            var hintsGroup = self._cachedHintsGroup[context];
            if (!hintsGroup) {
                self._cachedHintsGroup[context] = hintsGroup = [];
            }
            
            var hints = null;
            for (var i = 0; i < hintsGroup.length; i++) {
                var item = hintsGroup[i];
                var cacheToken = item[0];
                if (token.includes(cacheToken)) {
                    hints = item[1];
                    if (token === cacheToken) {
                        strict = false;
                    }
                    break;
                }
            }
            
            console.log('[OQL Standalone] Cache hit:', !!hints);
            
            if (strict && hints && hints.length >= limit) {
                hints = null;
            }
            
            // Fetch hints from server when cache missing
            if (!hints) {
                console.log('[OQL Standalone] Fetching hints from server...');
                try {
                    var response = await $.ajax({
                        url: '/web/dataset/call_kw',
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify({
                            jsonrpc: '2.0',
                            method: 'call',
                            params: {
                                model: self.model,
                                method: 'oql_hint',  // Use oql_hint for workbench
                                args: [content, cursorIndex, limit],
                                kwargs: {}
                            },
                            id: Math.floor(Math.random() * 1000000)
                        }),
                        dataType: 'json'
                    });
                    
                    console.log('[OQL Standalone] Server response:', response);
                    
                    if (response.error) {
                        console.error('[OQL] Failed to fetch hints:', response.error);
                        hints = [];
                    } else {
                        hints = response.result || [];
                    }
                } catch (error) {
                    console.error('[OQL] AJAX error:', error);
                    hints = [];
                }
                
                // Update cache
                hintsGroup.push([token, hints]);
                hintsGroup.sort(function(a, b) {
                    return b[0].length - a[0].length;
                });
            }

            console.log('[OQL Standalone] Hints count before filter:', hints.length);
            
            // Filter and sort hints
            hints = self._filterAndSortHints(hints, token);
            
            console.log('[OQL Standalone] Hints count after filter:', hints.length);

            // Generate hint list
            var hintList = hints.map(function(item) {
                return {
                    text: item.value,
                    displayText: item.value,
                    className: 'oql-hint-' + item.type,
                    render: function(el, cm, data) {
                        self._renderHintItem(el, item, token);
                    }
                };
            });

            console.log('[OQL Standalone] Returning hints:', hintList.length);
            
            return {
                list: hintList,
                from: from,
                to: to
            };
        },

        /**
         * Render a single hint item
         * @private
         */
        _renderHintItem: function(el, item, token) {
            var text = item.value;
            var lowerText = text.toLowerCase();
            var tokenLower = token.toLowerCase();
            var matchIndex = lowerText.indexOf(tokenLower);

            var container = document.createElement('div');
            container.className = 'oql-hint-item oql-hint-' + item.type;
            
            var typeMarker = document.createElement('div');
            typeMarker.className = 'type-marker';
            typeMarker.textContent = item.type.charAt(0).toUpperCase();
            
            var content = document.createElement('div');
            content.className = 'oql-hint-content';
            
            if (matchIndex >= 0) {
                var before = text.substring(0, matchIndex);
                var match = text.substring(matchIndex, matchIndex + token.length);
                var after = text.substring(matchIndex + token.length);
                content.innerHTML = before + '<strong>' + match + '</strong>' + after;
            } else {
                content.textContent = text;
            }
            
            container.appendChild(typeMarker);
            container.appendChild(content);
            
            if (item.desc) {
                var desc = document.createElement('span');
                desc.className = 'oql-hint-desc';
                desc.textContent = item.desc;
                container.appendChild(desc);
            }
            
            el.appendChild(container);
        },

        /**
         * Get current token at cursor position
         * @private
         */
        _getCurrentToken: function(cm) {
            var cursor = cm.getCursor();
            var lineText = cm.getLine(cursor.line);
            var prefix = lineText.substring(0, cursor.ch);
            var token = this._getLastToken(prefix);
            
            if (token === '.' || token === '(') {
                return '';
            }
            return token;
        },

        /**
         * Get last token from string
         * @private
         */
        _getLastToken: function(str) {
            var quoteInfo = this._getQuoteInfo(str);
            
            if (quoteInfo.inQuotes && quoteInfo.lastQuoteIndex !== -1) {
                return str.substring(quoteInfo.lastQuoteIndex);
            }
            
            var match = str.match(/(\w*|[^\w\s]*)$/);
            return match ? match[0] : '';
        },

        /**
         * Get quote information from text
         * @private
         */
        _getQuoteInfo: function(text) {
            var inQuotes = false;
            var lastQuoteIndex = -1;
            var i = 0;
            
            while (i < text.length) {
                if (text[i] === "'") {
                    if (inQuotes) {
                        if (i + 1 < text.length && text[i + 1] === "'") {
                            i += 2;
                            continue;
                        } else {
                            inQuotes = false;
                            lastQuoteIndex = i;
                        }
                    } else {
                        inQuotes = true;
                        lastQuoteIndex = i;
                    }
                }
                i++;
            }
            
            return { inQuotes: inQuotes, lastQuoteIndex: lastQuoteIndex };
        },

        /**
         * Filter and sort hints based on token
         * @private
         */
        _filterAndSortHints: function(hints, token) {
            if (!token) return hints;
            
            if (token.startsWith("'")) token = token.substring(1);
            if (token.endsWith("'")) token = token.substring(0, token.length - 1);
            
            var tokenLower = token.toLowerCase();
            var self = this;  // Capture 'this' for use in callbacks

            return hints
                .map(function(item) {
                    var value = item.value.toLowerCase();
                    var score = 0;

                    if (value.startsWith(tokenLower)) {
                        score = 3;
                    } else if (value.includes(tokenLower)) {
                        score = 2;
                    } else {
                        var distance = self._levenshteinDistance(tokenLower, value);
                        var maxLen = Math.max(token.length, value.length);
                        score = 1 - (distance / maxLen);
                    }

                    return Object.assign({}, item, { score: score });
                })
                .filter(function(item) {
                    return item.score > 0.3;
                })
                .sort(function(a, b) {
                    return b.score - a.score;
                });
        },

        /**
         * Calculate Levenshtein distance
         * @private
         */
        _levenshteinDistance: function(s, t) {
            if (s.length === 0) return t.length;
            if (t.length === 0) return s.length;

            var matrix = [];

            for (var i = 0; i <= s.length; i++) {
                matrix[i] = [i];
            }
            for (var j = 0; j <= t.length; j++) {
                matrix[0][j] = j;
            }

            for (var i = 1; i <= s.length; i++) {
                for (var j = 1; j <= t.length; j++) {
                    var cost = s[i - 1] === t[j - 1] ? 0 : 1;
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j - 1] + cost
                    );
                }
            }

            return matrix[s.length][t.length];
        }
    };

    // Export to global scope for standalone use
    window.OQLEditorCore = OQLEditorCore;

})(window);
