OQL - Odoo Query Language
=========================

Query Odoo ORM models with intuitive, business-focused syntax instead of complex technical domains.

Overview
--------

OQL (Odoo Query Language) transforms how you query data in Odoo. Instead of constructing verbose, nested domain expressions, you write queries that reflect business requirements directly.

The Problem
~~~~~~~~~~~

Traditional Odoo domain queries require deep technical knowledge and often multiple search operations. Consider finding waterproof Danner boots in EU sizes 40-40.5::

    # Step 1: Find the category records
    boot_catg = env['product.category'].search([
        ('name', '=', 'Boot'),
        ('level', '=', 'CatgS')
    ])
    danner_brand = env['product.category'].search([
        ('name', '=', 'Danner'),
        ('level', '=', 'Brand'),
        ('parent_id', 'child_of', boot_catg.ids)
    ])

    # Step 2: Find the attribute and its values
    size_values = env['product.attribute.value'].search([
        ('attribute_id.name', 'like', 'EU Shoe Size'),
        ('name', 'in', ['40', '40.5'])
    ])

    # Step 3: Find waterproof tags
    waterproof_tags = env['product.template.tag'].search([
        ('name', 'like', 'Waterproof')
    ])

    # Step 4: Construct the domain
    domain = [
        ('categ_id', 'child_of', danner_brand.ids),
        ('product_template_attribute_value_ids.product_attribute_value_id', 'in', size_values.ids),
        ('tag_ids', 'in', waterproof_tags.ids)
    ]
    products = env['product.product'].search(domain)

This approach has several issues:

- Requires multiple preparatory searches to get reference IDs
- Deep understanding of Odoo's internal relational structure
- Complex nested domains with child_of, OR logic, and multi-level relationships
- Business users cannot write or verify such queries
- Difficult to maintain when business requirements change

The OQL Solution
~~~~~~~~~~~~~~~~

The same query in OQL::

    products = env['product.product'].searcho(
        "CatgS = 'Boot' and Brand = 'Danner' and EuShoeSize in ('40', '40.5') and Waterproof"
    )

Benefits:

- **Business-focused**: Uses terms like "Waterproof" instead of field paths
- **Intuitive**: Reads like natural language requirements
- **Maintainable**: Easy to modify and understand
- **Accessible**: Business analysts can write and review queries

Core Concepts
-------------

OQL simplifies queries through three key concepts: Terms, the ``.`` operator, and Aliases.

1. Terms - Business Terminology Abstraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Terms map business concepts to actual database records. They allow you to query using meaningful names instead of technical identifiers.

Defining Terms
**************

There are two ways to define what records a term selects:

**Method 1: Domain Configuration**

Configure terms through ``oql.term.domain`` records with Odoo domain syntax::

    # Create a term for weather-related tags
    term_weather = env['oql.term'].create({'name': 'WeatherAware'})

    # Define domain to select relevant records
    env['oql.term.domain'].create({
        'term_id': term_weather.id,
        'model_id': product_tag_model.id,
        'name': 'WeatherSelector',
        'domain': "[('name', '=like', 'Weather:%')]"
    })

Now ``WeatherAware`` automatically matches any tag with name starting with "Weather:".

**Method 2: Relationship Fields**

Add Many2one or Many2many fields referencing ``oql.term`` on your business models::

    class ProductAttribute(models.Model):
        _name = 'product.attribute'
        
        name = fields.Char('Name')
        term_ids = fields.Many2many('oql.term', string='Terms')

Users can then associate terms with records through the UI::

    size_attr = env['product.attribute'].search([('name', '=', 'EU Size')])
    eu_size_term = env['oql.term'].create({'name': 'EuShoeSize'})
    size_attr.term_ids = [(4, eu_size_term.id)]

When querying ``EuShoeSize``, OQL finds all attributes linked to this term.

Custom Query Logic
******************

For advanced scenarios, implement ``__oql_bin__`` method on your model to control how term queries execute::

    class ProductAttribute(models.Model):
        _name = 'product.attribute'
        
        def __oql_bin__(self, term, opr, value, value_term):
            """Custom logic for term-based binary operations."""
            if term.domain == 'self.term_ids':
                # Search attribute values matching the criteria
                return self.value_ids.search([
                    ('id', 'in', self.value_ids.ids),
                    ('name', opr, value)
                ])
            raise NotImplementedError()

This allows ``EuShoeSize in ('40', '40.5')`` to return specific attribute value records rather than just attributes.

Using Terms in Queries
**********************

Once defined, use terms directly in queries::

    # Find products with EU Size 40
    products = env['product.product'].searcho("EuShoeSize = '40'")

    # Find products with multiple size options
    products = env['product.product'].searcho("EuShoeSize in ('40', '40.5')")

    # Find products tagged as waterproof
    products = env['product.product'].searcho("Waterproof")

2. The ``.`` Operator - Has/Contains Semantics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The dot operator expresses "has" or "contains" relationships. It checks whether a field contains records matching specified criteria.

Basic Usage
***********

::

    # Products that have waterproof tags
    products = env['product.product'].searcho("tag_ids.Waterproof")

    # Equivalent explicit syntax (dot at root is optional)
    products = env['product.product'].searcho(".Waterproof")

Nested Paths
************

Chain the dot operator to navigate relationships::

    # Products whose tags have the Waterproof term
    products = env['product.product'].searcho("product.tag_ids.Waterproof")

Combining with Conditions
*************************

Use dots with comparison operators::

    # Products with tags named specifically "Waterproof:GTX"
    products = env['product.product'].searcho("tag_ids.name = 'Waterproof:GTX'")

3. Aliases - Path Simplification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Aliases shorten long field paths and enable intelligent shorthand notation.

Name Simplification
*******************

Map verbose paths to concise names::

    # Configuration
    rule = env['oql.alias'].create({'model_id': product_model.id})
    env['oql.alias.line'].create({
        'rule_id': rule.id,
        'alias': 'spu',
        'path': 'product_tmpl_id.default_code',
        'enable_shorthand': False
    })

    # Usage - instead of:
    products = env['product.product'].searcho("product_tmpl_id.default_code = 'BOOT-001'")

    # Write:
    products = env['product.product'].searcho("spu = 'BOOT-001'")

Shorthand Notation
******************

Enable automatic field resolution based on value types::

    # Configuration - enable shorthand for attribute values
    env['oql.alias.line'].create({
        'rule_id': rule.id,
        'alias': 'attr_vals',
        'path': 'product_attribute_value_ids',
        'enable_shorthand': True  # Enable type-based matching
    })

    # When you write:
    products = env['product.product'].searcho("product.attribute.value recordset")

    # OQL automatically resolves to:
    # product.product.product_attribute_value_ids

The system matches value types to find the correct field path. Each model can have only one shorthand-enabled path per value type, ensuring unambiguous resolution.

Practical Example
*****************

::

    # Setup aliases for product model
    rule = env['oql.alias'].create({'model_id': product_model.id})

    # Alias for attribute values (with shorthand)
    env['oql.alias.line'].create({
        'rule_id': rule.id,
        'alias': 'attr_val_records',
        'path': 'attribute_value_ids',
        'enable_shorthand': True
    })

    # Alias for attribute records (with shorthand)
    env['oql.alias.line'].create({
        'rule_id': rule.id,
        'alias': 'attrs_records',
        'path': 'attribute_value_ids.attribute_id',
        'enable_shorthand': True
    })

    # Alias for tag names (without shorthand - requires full expression)
    env['oql.alias.line'].create({
        'rule_id': rule.id,
        'alias': 'tags',
        'path': 'tag_ids.name',
        'enable_shorthand': False
    })

    # Usage
    products = env['product.product'].searcho("tags = 'Waterproof:GTX'")

Query Syntax
------------

OQL supports familiar SQL-like syntax for building complex queries.

Comparison Operators
~~~~~~~~~~~~~~~~~~~~

::

    # Equality
    searcho("name = 'Cold Boot'")

    # Inequality
    searcho("name != 'Hot Boot'")

    # Greater/Less Than
    searcho("age > 18")
    searcho("price <= 100")

    # LIKE patterns
    searcho("name like 'Boot%'")

    # IN clause
    searcho("Size in ('40', '40.5', '41')")

Logical Operators
~~~~~~~~~~~~~~~~~

::

    # AND
    searcho("Brand = 'Danner' and Waterproof")

    # OR
    searcho("Size = '40' or Size = '40.5'")

    # Combined
    searcho("Brand = 'Danner' and (Size = '40' or Size = '40.5')")

Parentheses for Grouping
~~~~~~~~~~~~~~~~~~~~~~~~

::

    # Group conditions explicitly
    searcho("(Brand = 'Danner' or Brand = 'Merrell') and Waterproof")

    # Complex nesting
    searcho("(Size in ('40', '40.5') and Waterproof) or (Size = '42' and Breathable)")

Unary Expressions
~~~~~~~~~~~~~~~~~

Check for existence without specifying values::

    # Products that have any tags
    searcho("tag_ids")

    # Products that have attribute values
    searcho("attribute_value_ids")

    # Products with the Waterproof term
    searcho("Waterproof")

Complete Example
----------------

Here's a complete example showing all concepts working together:

Model Setup
~~~~~~~~~~~

::

    class Product(models.Model):
        _name = 'product.product'
        
        name = fields.Char('Name')
        attribute_value_ids = fields.One2many('product.attribute.value', 'product_id')
        tag_ids = fields.One2many('product.tag', 'product_id')


    class ProductAttribute(models.Model):
        _name = 'product.attribute'
        
        name = fields.Char('Name')
        value_ids = fields.One2many('product.attribute.value', 'attribute_id')
        term_ids = fields.Many2many('oql.term', string='Terms')
        
        def __oql_bin__(self, term, opr, value, value_term):
            if term.domain == 'self.term_ids':
                return self.value_ids.search([
                    ('id', 'in', self.value_ids.ids),
                    ('name', opr, value)
                ])
            raise NotImplementedError()


    class ProductTag(models.Model):
        _name = 'product.tag'
        
        name = fields.Char('Name')
        product_id = fields.Many2one('product.product')
        term_ids = fields.Many2many('oql.term', string='Terms')

Term Configuration
~~~~~~~~~~~~~~~~~~

::

    # Create terms
    term_eu_size = env['oql.term'].create({'name': 'EuShoeSize'})
    term_waterproof = env['oql.term'].create({'name': 'Waterproof'})
    term_brand_danner = env['oql.term'].create({'name': 'BrandDanner'})

    # Link terms to attributes
    eu_size_attr = env['product.attribute'].search([('name', '=', 'EU Size')])
    eu_size_attr.term_ids = [(4, term_eu_size.id)]

    # Link terms to tags via domain
    waterproof_tag_model = env['ir.model'].search([('model', '=', 'product.tag')])
    env['oql.term.domain'].create({
        'term_id': term_waterproof.id,
        'model_id': waterproof_tag_model.id,
        'domain': "[('name', '=like', 'Waterproof%')]"
    })

Alias Configuration
~~~~~~~~~~~~~~~~~~~

::

    product_model = env['ir.model'].search([('model', '=', 'product.product')])
    rule = env['oql.alias'].create({'model_id': product_model.id})

    env['oql.alias.line'].create({
        'rule_id': rule.id,
        'alias': 'attr_vals',
        'path': 'attribute_value_ids',
        'enable_shorthand': True
    })

    env['oql.alias.line'].create({
        'rule_id': rule.id,
        'alias': 'tags',
        'path': 'tag_ids.name',
        'enable_shorthand': False
    })

Query Examples
~~~~~~~~~~~~~~

::

    # Simple term query
    boots = env['product.product'].searcho("CatgS = 'Boot'")

    # Multiple conditions
    danner_boots = env['product.product'].searcho(
        "CatgS = 'Boot' and Brand = 'Danner'"
    )

    # Size range with IN clause
    sized_boots = env['product.product'].searcho(
        "EuShoeSize in ('40', '40.5')"
    )

    # Complete business requirement
    result = env['product.product'].searcho(
        "CatgS = 'Boot' and "
        "Brand = 'Danner' and "
        "EuShoeSize in ('40', '40.5') and "
        "Waterproof"
    )

Installation
------------

1. Install the Python dependency::

    pip install lark

2. Install the OQL module in your Odoo instance

3. Configure terms and aliases for your models

Best Practices
--------------

When to Use OQL
~~~~~~~~~~~~~~~

- Complex queries involving multiple related models
- User-facing search features where readability matters
- Business rules that change frequently
- Scenarios where non-developers need to understand queries

When to Use Traditional Domains
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Simple, single-model queries
- Performance-critical operations where domain optimization matters
- Cases requiring very specific Odoo ORM features

Performance Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

- OQL adds a parsing and resolution layer; for simple queries, traditional domains may be faster
- Term lookups are cached after first load
- Complex alias chains may impact performance; monitor query execution times
- Use ``enable_shorthand`` judiciously; it adds type-checking overhead

Naming Conventions
~~~~~~~~~~~~~~~~~~

- Use clear, business-oriented term names (e.g., ``EuShoeSize`` not ``eu_size_attr``)
- Keep aliases short but descriptive (e.g., ``spu`` for stock keeping unit)
- Document term meanings for team reference

Advanced Features
-----------------

Custom Hint Methods
~~~~~~~~~~~~~~~~~~~

Implement ``__oql_hnt__`` to provide autocomplete suggestions::

    def __oql_hnt__(self, opr: str):
        """Return hints for query completion."""
        if opr == "?":
            return self.value_ids  # Return possible record completions
        else:
            return self.value_ids.mapped("name")  # Return value suggestions

Lazy Loading
~~~~~~~~~~~~

OQL uses lazy loading for term metadata to minimize startup overhead. Terms are loaded on first use, then cached.

Error Handling
~~~~~~~~~~~~~~

OQL provides clear error messages when:

- A term is not found
- An alias is ambiguous
- A field path does not exist
- Type mismatches occur in shorthand resolution

Migration from Domains
----------------------

Converting existing domain queries to OQL:

1. Identify business concepts in your domain (these become Terms)
2. Map field paths to shorter aliases where appropriate
3. Replace technical field references with business terms
4. Test thoroughly to ensure equivalent results

Example conversion::

    # Before (Domain)
    domain = [
        '&',
        ('categ_id.name', '=', 'Boot'),
        ('tag_ids.name', '=like', 'Waterproof%')
    ]

    # After (OQL)
    query = "CatgS = 'Boot' and Waterproof"

Support and Contribution
------------------------

For issues, feature requests, or contributions, visit:
https://github.com/chrisking94/odoo_addons/tree/main/oql

License
-------

LGPL-3
