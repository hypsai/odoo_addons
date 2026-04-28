OQL - Odoo Query Language
=========================

Query Odoo ORM models with intuitive, business-focused syntax instead of complex technical domains.

Overview
--------

OQL (Odoo Query Language) transforms how you query data in Odoo. Instead of constructing verbose, nested domain expressions, you write queries that reflect business requirements directly.

The Problem
~~~~~~~~~~~

How many lines of code does it take to find waterproof Danner boots in EU sizes 40-40.5?
-----------------------------------------------------------------------------------------

**Traditional Odoo Domain Approach (❌ Complex & Verbose)**

With traditional Odoo domains, you need **4 preparatory searches + 1 complex domain**:

.. code-block:: python

    # Step 1: Find category records (2 searches)
    boot_catg = env['product.category'].search([
        ('name', '=', 'Boot'),
        ('level', '=', 'CatgS')
    ])
    danner_brand = env['product.category'].search([
        ('name', '=', 'Danner'),
        ('level', '=', 'Brand'),
        ('parent_id', 'child_of', boot_catg.ids)
    ])

    # Step 2: Find attribute values (1 search)
    size_values = env['product.attribute.value'].search([
        ('attribute_id.name', 'like', 'EU Shoe Size'),
        ('name', 'in', ['40', '40.5'])
    ])

    # Step 3: Find waterproof tags (1 search)
    waterproof_tags = env['product.template.tag'].search([
        ('name', 'like', 'Waterproof')
    ])

    # Step 4: Construct and execute the domain
    domain = [
        ('categ_id', 'child_of', danner_brand.ids),
        ('product_template_attribute_value_ids.product_attribute_value_id', 'in', size_values.ids),
        ('tag_ids', 'in', waterproof_tags.ids)
    ]
    products = env['product.product'].search(domain)

.. attention::

   **Problems with this approach:**

   - 30+ lines of code for a simple business requirement
   - Requires deep knowledge of Odoo's internal data structure
   - Multiple database queries just to build the domain
   - Business users cannot read, write, or verify the logic
   - Fragile: breaks when data model changes

OQL Solution (✅ Simple & Intuitive)
=====================================

**The same query in 1 line:**

.. code-block:: python

    products = env['product.product'].searcho(
        "CatgS = 'Boot' and Brand = 'Danner' and EuShoeSize in ('40', '40.5') and Waterproof"
    )

.. important::

   **Benefits:**

   - ✅ **Business-focused**: Uses terms like "Waterproof" instead of field paths
   - ✅ **Intuitive**: Reads like natural language requirements
   - ✅ **Maintainable**: One line, easy to modify and understand
   - ✅ **Accessible**: Business analysts can write and review queries
   - ✅ **Efficient**: No preparatory searches needed

Quick Start
-----------

Get started with OQL in 3 steps:

**1. Install**

Install the OQL module and its dependency::

    pip install lark

**2. Configure Terms**

Navigate to **Settings > Technical > OQL > Terms** and create your first term (e.g., "Waterproof"). Add domain rules or link it to records via the UI.

**3. Query**

Use ``searcho()`` instead of ``search()``::

    products = env['product.product'].searcho("Waterproof and Size = '40'")

That's it! Start writing business-focused queries immediately.

For detailed configuration options and advanced features, see Core Concepts below.

.. note::
   This documentation is currently being improved. More examples and detailed guides are coming soon.

Core Concepts
-------------

OQL simplifies queries through two fundamental concepts: **Terms** and **Aliases**. These abstractions let you write queries in business language rather than technical field paths.

1. Terms - Business Terminology Abstraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Terms map business concepts to actual database records. Instead of writing complex domain filters, you define meaningful names that represent specific record sets.

For example, instead of filtering tags with ``('name', '=like', 'Waterproof%')``, you simply use the term ``Waterproof`` in your query.

Defining Terms via UI
*********************

**Method 1: Domain-Based Configuration**

Create terms and configure their selection rules directly through the Odoo interface:

1. Navigate to **Settings > Technical > OQL > Terms** menu
2. Create a new term (e.g., "Waterproof")
3. Add domain rules to specify which records this term selects

.. image:: static/description/term_config.png
   :alt: Term configuration with domain rules
   :align: center
   :width: 800px

Each term can have multiple domain rules for different models. When you use the term in a query, OQL automatically applies the appropriate domain to filter records.

**Method 2: Relationship Field Association**

For more flexible term assignment, add a Many2many field to your business models:

.. code-block:: python

    class ProductAttribute(models.Model):
        _inherit = 'product.attribute'
        
        term_ids = fields.Many2many('oql.term', string='Terms')

Note: Expose this field in the form view so users can associate terms with records through the UI.

Now when you query ``EuShoeSize``, OQL finds all attributes that have been tagged with the "EuShoeSize" term through the interface.

Using Terms in Queries
**********************

Once configured, use terms directly in your queries:

.. code-block:: python

    # Find products with EU Size 40
    products = env['product.product'].searcho("EuShoeSize = '40'")

    # Find products with multiple size options
    products = env['product.product'].searcho("EuShoeSize in ('40', '40.5')")

    # Find products tagged as waterproof
    products = env['product.product'].searcho("Waterproof")

The term automatically resolves to the underlying records based on your configuration.

2. Aliases - Path Simplification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Aliases shorten long field paths into concise, memorable names. They eliminate the need to remember complex relational chains.

Configuring Aliases via UI
**************************

Set up aliases through the OQL interface:

1. Navigate to **Settings > Technical -> OQL > Aliases** menu
2. Select the target model (e.g., ``product.product``)
3. Add alias rules mapping short names to field paths

.. image:: static/description/alias_config.png
   :alt: Alias configuration interface
   :align: center
   :width: 800px

**Name Simplification**

Map verbose paths to short aliases:

- ``product_tmpl_id.default_code`` → ``spu``
- ``categ_id.complete_name`` → "category"
- ``partner_id.country_id.name`` → ``country``

**Shorthand Notation**

Enable intelligent type-based resolution by checking the "Enable Shorthand" option. When enabled, OQL automatically matches value types to find the correct field path.

For example, if you enable shorthand for ``tags`` for `tag_ids` on the product model, you can write:

.. code-block:: python

    # Instead of:
    products = env['product.product'].searcho("tags.Waterproof'")

    # Simply use the term directly (OQL resolves the path automatically):
    products = env['product.product'].searcho("Waterproof")

Each model can have only one shorthand-enabled path per value type, ensuring unambiguous resolution.

Using Aliases in Queries
************************

Once configured, use aliases to simplify your queries:

.. code-block:: python

    # Without alias:
    products = env['product.product'].searcho("product_tmpl_id.default_code = 'BOOT-001'")

    # With alias 'spu':
    products = env['product.product'].searcho("spu = 'BOOT-001'")

3. Operator Overloading - Custom Query Logic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For advanced scenarios, you can customize how terms behave in queries by implementing the ``__oql_bin__`` method on your models.

Why Operator Overloading?
*************************

By default, when you use a term like ``EuShoeSize = '40'``, OQL finds records associated with that term. But sometimes you need more sophisticated logic.

For example, ``EuShoeSize`` might be linked to ``product.attribute`` records, but you actually want to query based on ``product.attribute.value`` records. Operator overloading lets you define this custom behavior.

Implementing __oql_bin__
************************

Add the ``__oql_bin__`` method to your model:

.. code-block:: python

    class ProductAttribute(models.Model):
        _inherit = 'product.attribute'
        
        def __oql_bin__(self, term, opr, value, value_term):
            """Custom logic for term-based binary operations.
            
            Args:
                term: The Term object being queried
                opr: The operator (=, !=, in, etc.)
                value: The value being compared
                value_term: Value term if applicable
            """
            if term.domain == 'self.term_ids':
                # Search attribute values matching the criteria
                return self.value_ids.search([
                    ('id', 'in', self.value_ids.ids),
                    ('name', opr, value)
                ])
            raise NotImplementedError()

This implementation allows ``EuShoeSize in ('40', '40.5')`` to:

1. Find attributes tagged with the "EuShoeSize" term
2. Search their ``value_ids`` for values matching '40' or '40.5'
3. Return the matching ``product.attribute.value`` records
4. Use these records to filter products

When to Use Operator Overloading
********************************

Use ``__oql_bin__`` when:

- Terms are linked to parent records but you need to query child records
- You need custom filtering logic beyond simple domain matching
- The default term resolution doesn't match your business requirements

Example Use Cases
*****************

**Case 1: Attribute to Value Resolution**

As shown above, resolve from attributes to their values for size/colour queries.


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
