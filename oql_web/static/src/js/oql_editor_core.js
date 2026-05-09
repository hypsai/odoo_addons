/**
 * OQL Editor Core - Reusable CodeMirror-based OQL editor
 */
odoo.define('oql_web.oql_editor_core', function (require) {
    "use strict";

    var Class = require('web.Class');
    var ajax = require('web.ajax');

    /**
     * OQL Editor Core Class
     * @param {Object} options Configuration options
     * @param {jQuery} options.container jQuery container element
     * @param {string} options.model Odoo model name for fetching hints
     * @param {number} [options.res_id] Record ID (optional, for field context)
     * @param {string} [options.fieldName] Field name (optional, for field context)
     * @param {boolean} [options.readonly=false] Whether editor is readonly
     * @param {boolean} [options.lineNumbers=false] Show line numbers
     * @param {Function} [options.onSearch] Callback when Enter is pressed (for search bar mode)
     * @param {Function} [options.onChange] Callback when content changes (for field mode)
     * @param {Array} [options.history=[]] Initial history items
     * @param {Function} [options.onHistorySelect] Callback when history item is selected
     */
    var OQLEditorCore = Class.extend({
        init: function (options) {
            this.container = options.container;
            this.model = options.model;
            this.res_id = options.res_id || null;
            this.fieldName = options.fieldName || null;
            this.readonly = options.readonly || false;
            this.lineNumbers = options.lineNumbers || false;
            this.onSearch = options.onSearch || null;
            this.onChange = options.onChange || null;
            this.history = options.history || [];
            this.onHistorySelect = options.onHistorySelect || null;
            
            this.editor = null;
            this.$textarea = null;
            this._cachedHintsGroup = {};
            this.$historyDropdown = null;
            this.historyEditors = [];  // Store CodeMirror instances for history items
        },

        /**
         * Initialize the CodeMirror editor
         */
        start: function () {
            if (typeof CodeMirror === 'undefined') {
                console.error('[OQL] CodeMirror not loaded!');
                return Promise.reject(new Error('CodeMirror not loaded'));
            }

            var self = this;
            this.$textarea = $('<textarea placeholder="Enter OQL query..." style="width:100%;min-height:38px;"></textarea>');
            this.container.empty().append(this.$textarea);

            // Use requestAnimationFrame for better performance
            return new Promise(function (resolve) {
                requestAnimationFrame(function () {
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
        _getExtraKeys: function () {
            var self = this;
            var keys = {};

            // Enter key for search mode
            if (this.onSearch && !this.lineNumbers) {
                keys["Enter"] = function (cm) {
                    self.onSearch(cm.getValue());
                };
            }

            // Ctrl key for hint in field mode
            keys["Ctrl"] = function (cm) {
                self._showHint(cm, true);
            };

            return keys;
        },

        /**
         * Setup event listeners
         * @private
         */
        _setupEventListeners: function () {
            var self = this;
            var hintTimeout = null;

            // Always setup change listener for auto-hints
            this.editor.on('change', function (cm, change) {
                if (change.origin === '+input') {
                    // Notify onChange callback if provided
                    if (self.onChange) {
                        self.onChange(cm.getValue());
                    }
                    
                    // Debounce hint display (similar to PyCharm)
                    if (hintTimeout) {
                        clearTimeout(hintTimeout);
                    }
                    
                    hintTimeout = setTimeout(function() {
                        // Show hints on any character input (PyCharm-style)
                        self._showHint(cm);
                    }, 150); // 150ms debounce delay
                }
            });
        },

        /**
         * Get current editor value
         */
        getValue: function () {
            return this.editor ? this.editor.getValue() : '';
        },

        /**
         * Set editor value
         */
        setValue: function (value) {
            if (this.editor) {
                this.editor.setValue(value || '');
            }
        },

        /**
         * Focus the editor
         */
        focus: function () {
            if (this.editor) {
                this.editor.focus();
            }
        },

        /**
         * Destroy the editor instance
         */
        destroy: function () {
            if (this.editor) {
                this.editor.toTextArea();
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
        _showHint: function (cm, strict) {
            if (this.readonly) return;
            strict = strict || false;
            
            var self = this;
            CodeMirror.showHint(cm, async function (cm) {
                return await self._getHints(cm, strict);
            }, {
                'completeSingle': false
            });
        },

        /**
         * Get hints from cache or server
         * @param {Object} cm CodeMirror instance
         * @param {boolean} strict Strict matching mode
         * @private
         */
        _getHints: async function (cm, strict) {
            var self = this;
            var cursor = cm.getCursor();
            var doc = cm.getDoc();
            var content = doc.getValue();
            var cursor_index = doc.indexFromPos(cursor);  // Absolute position from document start
            var token = self._getCurrentToken(cm);
            var prefix = content.substring(0, cursor_index - token.length);  // Use absolute position
            var context = prefix.trim();
            var tokenStart = cursor_index - token.length;  // Use absolute position
            var from = doc.posFromIndex(tokenStart);  // Convert back to {line, ch}
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
            
            if (strict && hints && hints.length >= limit) {
                hints = null;
            }
            
            // Fetch hints from server when cache missing
            if (!hints) {
                hints = await ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                    model: self.model,
                    method: 'hinto',
                    args: [content, cursor_index, limit],
                    kwargs: {}
                }).catch(function (error) {
                    console.error('[OQL Core] Failed to fetch hints:', error);
                    return [];
                });
                hints = hints || [];
                
                // Update cache
                hintsGroup.push([token, hints]);
                hintsGroup.sort(function (a, b) {
                    return b[0].length - a[0].length;
                });
            }

            // Filter and sort hints
            hints = self._filterAndSortHints(hints, token);

            // Generate hint list
            var self = this;
            var hintList = hints.map(function (item) {
                return {
                    text: item.value,
                    displayText: item.value,
                    className: 'oql-hint-' + item.type,
                    hintClass: 'compact-hint',
                    render: function (el, cm, data) {
                        self._renderHintItem(el, item, token);
                    }
                };
            });

            return {
                list: hintList,
                from: from,
                to: to
            };
        },

        /**
         * Render a single hint item
         * @param {HTMLElement} el Element to render into
         * @param {Object} item Hint item data
         * @param {string} token Current token for highlighting
         * @private
         */
        _renderHintItem: function (el, item, token) {
            var text = item.value;
            var lowerText = text.toLowerCase();
            var tokenLower = token.toLowerCase();
            var matchIndex = lowerText.indexOf(tokenLower);

            // Create container
            var container = document.createElement('div');
            container.className = 'oql-hint-item oql-hint-' + item.type;
            
            // Create type marker
            var typeMarker = document.createElement('div');
            typeMarker.className = 'type-marker';
            typeMarker.textContent = item.type.charAt(0).toUpperCase();
            
            // Create content
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
            
            // Assemble
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
         * @param {Object} cm CodeMirror instance
         * @private
         */
        _getCurrentToken: function (cm) {
            var cursor = cm.getCursor();
            var lineText = cm.getLine(cursor.line);
            var prefix = lineText.substring(0, cursor.ch);
            var token = this._getLastToken(prefix);
            
            // '.' and '(' are special tokens that precedes an empty token
            if (token === '.' || token === '(') {
                return '';
            }
            return token;
        },

        /**
         * Get previous token before cursor
         * @param {Object} cm CodeMirror instance
         * @private
         */
        _getPreviousToken: function (cm) {
            var cursor = cm.getCursor();
            var lineText = cm.getLine(cursor.line);
            var prefix = lineText.substring(0, cursor.ch);
            var token = this._getLastToken(prefix);
            
            if (token === '.') {
                return '.';
            }
            
            prefix = prefix.substring(0, prefix.length - token.length);
            prefix = prefix.replace(/\s*$/, '');
            token = this._getLastToken(prefix);
            return token;
        },

        /**
         * Get last token from string
         * @param {string} str Input string
         * @private
         */
        _getLastToken: function (str) {
            var quoteInfo = this._getQuoteInfo(str);
            
            if (quoteInfo.inQuotes && quoteInfo.lastQuoteIndex !== -1) {
                return str.substring(quoteInfo.lastQuoteIndex);
            }
            
            var match = str.match(/(\w*|[^\w\s]*)$/);
            return match ? match[0] : '';
        },

        /**
         * Get quote information from text
         * @param {string} text Input text
         * @private
         */
        _getQuoteInfo: function (text) {
            var inQuotes = false;
            var lastQuoteIndex = -1;
            var i = 0;
            
            while (i < text.length) {
                if (text[i] === "'") {
                    if (inQuotes) {
                        // Check for escaped quote
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
         * @param {Array} hints Hints array
         * @param {string} token Current token
         * @private
         */
        _filterAndSortHints: function (hints, token) {
            if (!token) return hints;
            
            // Remove quotes from token
            if (token.startsWith("'")) token = token.substring(1);
            if (token.endsWith("'")) token = token.substring(0, token.length - 1);
            
            var tokenLower = token.toLowerCase();
            var self = this;

            // Compute similarity score and sort
            return hints
                .map(function (item) {
                    var value = item.value.toLowerCase();
                    var score = 0;

                    // Prefix match - highest score
                    if (value.startsWith(tokenLower)) {
                        score = 3;
                    }
                    // Includes - medium score
                    else if (value.includes(tokenLower)) {
                        score = 2;
                    }
                    // Use Levenshtein distance
                    else {
                        var distance = self._levenshteinDistance(tokenLower, value);
                        var maxLen = Math.max(token.length, value.length);
                        score = 1 - (distance / maxLen);
                    }

                    return Object.assign({}, item, { score: score });
                })
                .filter(function (item) {
                    return item.score > 0.3;
                })
                .sort(function (a, b) {
                    return b.score - a.score;
                });
        },

        /**
         * Calculate Levenshtein distance between two strings
         * @param {string} s First string
         * @param {string} t Second string
         * @private
         */
        _levenshteinDistance: function (s, t) {
            if (s.length === 0) return t.length;
            if (t.length === 0) return s.length;

            var matrix = [];

            // Initialize matrix
            for (var i = 0; i <= s.length; i++) {
                matrix[i] = [i];
            }
            for (var j = 0; j <= t.length; j++) {
                matrix[0][j] = j;
            }

            // Compute distance
            for (var i = 1; i <= s.length; i++) {
                for (var j = 1; j <= t.length; j++) {
                    var cost = s[i - 1] === t[j - 1] ? 0 : 1;
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j] + 1,      // Deletion
                        matrix[i][j - 1] + 1,      // Insertion
                        matrix[i - 1][j - 1] + cost // Replacement
                    );
                }
            }

            return matrix[s.length][t.length];
        }
    });

    return OQLEditorCore;
});
