odoo.define('oql.oql_editor', function (require) {
    "use strict";

    const DebouncedField = require('web.basic_fields').DebouncedField;
    const fieldRegistry = require('web.field_registry');
    const ajax = require('web.ajax');

    const OQLEditor = DebouncedField.extend({
        className: 'o_oql_editor',
        supportedFieldTypes: ['char', 'text'],

        init: function (parent, name, record, options) {
            this._super.apply(this, arguments);
            this.model = record.model;
            this.isReadonly = this.mode === 'readonly';
            this._cachedHintsGroup = {};  // {context: [[value_token(list is order by this), hints]]}
        },

        start: function () {
            this._super.apply(this, arguments);
            this._initEditor();
            return Promise.resolve();
        },

        _getValue: function () {
            if (this.editor) {
                return this.editor.getValue();
            }
            return this.value;
        },

        _notifyChanges() {
            this.isDirty = !this._isLastSetValue(this._getValue());
            this._doDebouncedAction();
        },

        _initEditor: function () {
            const self = this;
            this.$textarea = $('<textarea>');
            this.$el.append(this.$textarea);

            // Load initial value.
            this.$textarea[0].value = this.value || '';

            this.editor = CodeMirror.fromTextArea(this.$textarea[0], {
                lineNumbers: true,
                mode: 'text/x-oql',
                readOnly: self.isReadonly,
                extraKeys: {
                    "Ctrl": (cm) => this._showHint(cm, true)
                }
            });

            // Listen editor code change.
            this.editor.on('change', (cm, change) => {
                // Notify odoo value change.
                self._notifyChanges();
                // Show hint automatically when operator is inputted.
                if (change.origin == '+input') {
                    const oprs = new Set(['.', ',', '=', '>', '<', '?', 'like', 'ilike', 'in', 'child_of', 'parent_of', 'not', 'and', 'or']);
                    const prevToken = self._getPreviousToken(cm);
                    const curToken = self._getCurrentToken(cm);
                    if (curToken === '.' || (curToken === '' && oprs.has(prevToken))) {
                        self._showHint(cm);
                    }
                }
            });

            // Assure editor to show content by refresh the editor.
            setTimeout(() => {
                this.editor.refresh();
            }, 100);
        },

        /**
         * Show hints with CodeMirror popup.
         * @param {*} cm CodeMirror instance.
         * @param {*} strict true: Match the value token strictly. false: Match only the prefix before value token.
         * This is very useful when update hints from server. Server can use the value token to filter hints in database query.
         * Which could help to generate hints that are more relevant.
         * @returns 
         */
        _showHint: function (cm, strict=false) {
            if (this.isReadonly) return;
            const self = this;

            // Show hints.
            // * Use `self` as captured `this`, or `this` will lost in the callback.
            CodeMirror.showHint(cm, async (cm) => await this._getHints(self, cm, strict), {
                'completeSingle': false
            });
        },

        _getHints: async (self, cm, strict=false) => {
            // Get token position range.
            const cursor = cm.getCursor();
            const doc = cm.getDoc();
            const content = doc.getValue();
            const cursor_index = doc.indexFromPos(cursor);
            const token = self._getCurrentToken(cm);
            const prefix = content.substring(0, cursor.ch - token.length);
            const context = prefix.trim();  // Simply use prefix as context.
            const tokenStart = cursor.ch - token.length;
            const from = { line: cursor.line, ch: tokenStart };
            const to = cursor;
            const limit = 100;

            // Load hints from cache.
            var hintsGroup = self._cachedHintsGroup[context];
            if (!hintsGroup) {
                self._cachedHintsGroup[context] = hintsGroup = [];
            }
            var hints = null;
            for (const item of hintsGroup) {
                // Find the best one.
                const cacheToken = item[0];
                if (token.includes(cacheToken)) {
                    hints = item[1];
                    if (token == cacheToken) {
                        strict = false;  // No need to retrieve database when fully matched cache hit.
                    }
                    break;
                }
            }
            if (strict && hints && hints.length >= limit) {
                hints = null;  // There might be better hints in the database that has not been retrieved.
            }
            // Fetch hints from server when cache missing.
            if (!hints) {
                hints = await self._rpc({
                    model: self.model,
                    method: 'get_oql_hints',
                    args: [[self.res_id], self.name, content, cursor_index, limit]
                });
                // Update cache.
                hintsGroup.push([token, hints]);
                hintsGroup.sort((a, b) => b[0].length - a[0].length);
            }

            // Filter and sort.
            hints = self._filterAndSortHints(hints, token);

            // Generate hint list.
            const hintList = hints.map(item => ({
                text: item.value,
                displayText: item.value,
                className: `oql-hint-${item.type}`,
                hintClass: 'compact-hint',
                render: (el, self, data) => {
                    const className = data.className;
                    const text = data.text;
                    const lowerText = text.toLowerCase();
                    const tokenLower = token.toLowerCase();
                    const matchIndex = lowerText.indexOf(tokenLower);

                    // Create container
                    const container = document.createElement('div');
                    container.className = `oql-hint-item ${className}`;
                    
                    // Create type mark.
                    const typeMarker = document.createElement('div');
                    typeMarker.className = 'type-marker';
                    typeMarker.textContent = item.type.charAt(0).toUpperCase();
                    
                    // Create content container.
                    const content = document.createElement('div');
                    content.className = 'oql-hint-content';
                    
                    if (matchIndex >= 0) {
                        const before = text.substring(0, matchIndex);
                        const match = text.substring(matchIndex, matchIndex + token.length);
                        const after = text.substring(matchIndex + token.length);
                        
                        content.innerHTML = `${before}<strong>${match}</strong>${after}`;
                    } else {
                        content.textContent = text;
                    }
                    
                    // Assemble.
                    container.appendChild(typeMarker);
                    container.appendChild(content);
                    if (item.desc) {
                        const desc = document.createElement('span');
                        desc.className = 'oql-hint-desc';
                        desc.textContent = item.desc;
                        container.appendChild(desc);
                    }
                    el.appendChild(container);
                }
            }));

            return {
                list: hintList,
                from: from,
                to: to
            };
        },

        _getCurrentToken: function (cm) {
            // Get the token right before cursor.
            const cursor = cm.getCursor();
            const lineText = cm.getLine(cursor.line);
            const prefix = lineText.substring(0, cursor.ch);

            const token = this._getLastToken(prefix);
            if (token === '.') { // Dot is a special token that precedes an empty token.
                return '';
            }
            return token;
        },

        _getPreviousToken: function (cm) {
            // Get the last 2nd token right before cursor.
            const cursor = cm.getCursor();
            const lineText = cm.getLine(cursor.line);

            let prefix = lineText.substring(0, cursor.ch);
            let token = this._getLastToken(prefix);
            if (token === '.') { // Dot is a special token that precedes an empty token.
                return '.';
            }
            prefix = prefix.substring(0, prefix.length-token.length);
            prefix = prefix.replace(/\s*$/, '')
            token = this._getLastToken(prefix);
            return token;
        },

        _getLastToken: function (str) {
            // Check if last token is in quote.
            const { inQuotes, lastQuoteIndex } = this._getQuoteInfo(str);
            if (inQuotes && lastQuoteIndex !== -1) {
                // Get substring from start quote to cursor.
                return str.substring(lastQuoteIndex);
            }
            return str.match(/(\w*|[^\w\s]*)$/)[0]  // Simply match last non-whitechar token.
        },

        _getQuoteInfo: function (text) {
            let inQuotes = false;
            let lastQuoteIndex = -1;
            let i = 0;
            
            while (i < text.length) {
                if (text[i] === "'") {
                    if (inQuotes) {
                        // In quote, check whether is double quote escape.
                        if (i + 1 < text.length && text[i + 1] === "'") {
                            i += 2; // Skip escaped quote.
                            continue;
                        } else {
                            // End quote.
                            inQuotes = false;
                            lastQuoteIndex = i;
                        }
                    } else {
                        // Start quote.
                        inQuotes = true;
                        lastQuoteIndex = i;
                    }
                }
                i++;
            }
            
            return { inQuotes, lastQuoteIndex };
        },

        _filterAndSortHints: function (hints, token) {
            if (!token) return hints;
            if (token.startsWith("'")) token = token.substring(1);
            if (token.endsWith("'")) token = token.substring(0, token.length-1);

            const tokenLower = token.toLowerCase();

            // Compute similarity score and sort.
            return hints
                .map(item => {
                    const value = item.value.toLowerCase();
                    let score = 0;

                    // Prefix match, highest score.
                    if (value.startsWith(tokenLower)) {
                        score = 3;
                    }
                    // Includes, medium score.
                    else if (value.includes(tokenLower)) {
                        score = 2;
                    }
                    // Else, use editing distance.
                    else {
                        const distance = this._levenshteinDistance(tokenLower, value);
                        const maxLen = Math.max(token.length, value.length);
                        score = 1 - (distance / maxLen);
                    }

                    return {...item, score};
                })
                .filter(item => item.score > 0.3)
                .sort((a, b) => b.score - a.score);
        },

        _levenshteinDistance: function (s, t) {
            // Highly effective editing distance computation.
            if (s.length === 0) return t.length;
            if (t.length === 0) return s.length;

            const matrix = [];

            // Initiate matrix.
            for (let i = 0; i <= s.length; i++) {
                matrix[i] = [i];
            }
            for (let j = 0; j <= t.length; j++) {
                matrix[0][j] = j;
            }

            // Compute distance.
            for (let i = 1; i <= s.length; i++) {
                for (let j = 1; j <= t.length; j++) {
                    const cost = s[i-1] === t[j-1] ? 0 : 1;
                    matrix[i][j] = Math.min(
                        matrix[i-1][j] + 1,   // Deletion
                        matrix[i][j-1] + 1,   // Insertion
                        matrix[i-1][j-1] + cost // Replacement
                    );
                }
            }

            return matrix[s.length][t.length];
        },

        _onKeydown: function (e) {
            if (this.isReadonly) {
                return;
            }
            // Keep this function to stop 'Tab' from switching focus to another control.
        },
    });

    fieldRegistry.add('oql_editor', OQLEditor);
    return OQLEditor;
});