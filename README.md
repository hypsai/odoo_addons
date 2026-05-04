# Odoo Addons

A collection of custom Odoo modules designed to enhance user experience and provide developers with flexible tools.

---

## Available Addons

| Module               | Description                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| [MCP Framework](./mcp_base)      | Transform Odoo into AI-ready MCP Server with one decorator                  |
| [OQL](./oql)                     | Query Odoo with intuitive, business-focused syntax                        |
| [OQL Web](./oql_web)             | Advanced search interface with syntax highlighting and autocomplete       |
| [Web Widget Pill Icon](./web_widget_pill_icon) | Dynamic icons & semantic colors for any field                             |
| [Web Widget YAML](./web_widget_yaml)           | Advanced YAML editor with customizable Ace editor options               |

---

## Highlights

### MCP Framework
Transform your Odoo into a Model Context Protocol (MCP) Server for seamless AI integration.
- One-line setup with `@mcp_tool` decorator
- Automatic JSON schema generation from type hints
- Implements MCP Streamable HTTP protocol

### OQL - Odoo Query Language
Write queries in business language instead of technical domain expressions.
- Use terms like "Waterproof" instead of complex field paths
- SQL-like syntax: AND, OR, IN, LIKE operators
- Configure entirely through Odoo UI, no code needed
- Reduce 30+ lines of domain code to a single line

### OQL Web
Enhanced search interface that transforms the native Odoo search bar.
- Real-time syntax highlighting
- Smart autocomplete for terms and aliases
- Automatic search history management
- Toggle between native and OQL search instantly

### Web Widget Pill Icon
Transform text, selection, or numeric fields into stylish pills and badges.
- Configure icons and colors entirely in XML options
- Works with Selection, Char, Integer, and Many2one fields
- Built-in CSS fixes for Odoo 15 List View alignment
- Support for global styling classes (pill, outline, sm)

### Web Widget YAML
Advanced YAML code editor extending the standard Ace Editor.
- Syntax highlighting and validation
- Customizable editor options
- Ideal for configuration management
- Seamless integration with Odoo forms

---

For detailed documentation and installation instructions, click on any module link above.

If you find these modules useful, please consider giving this repository a star.