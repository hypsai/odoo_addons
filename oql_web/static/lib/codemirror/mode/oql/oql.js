// CodeMirror OQL mode
(function(mod) {
  if (typeof exports == "object" && typeof module == "object") // CommonJS
    mod(require("../../lib/codemirror"));
  else if (typeof define == "function" && define.amd) // AMD
    define(["../../lib/codemirror"], mod);
  else // Plain browser env
    mod(CodeMirror);
})(function(CodeMirror) {
  "use strict";

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
});
