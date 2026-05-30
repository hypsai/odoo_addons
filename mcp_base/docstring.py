"""
Lightweight docstring parser supporting Google, NumPy, and Sphinx styles.

Based on the proven docstring_parser library (https://github.com/rr-/docstring_parser)
Simplified for zero-dependency usage in Odoo MCP Framework.
"""
import inspect
import re
from .typeutil import docstring_type_to_json_type


def _clean_docstring(text):
    """Clean docstring according to PEP-0257."""
    return inspect.cleandoc(text) if text else ""


def _parse_google_style(docstring):
    """Parse Google-style docstring parameters.
    
    Format:
        Args:
            param_name: Description here
            param_type param_name: Description with type
    
    Returns:
        dict: Mapping of parameter names to descriptions
    """
    params = {}
    lines = docstring.split('\n')
    in_params_section = False
    current_param = None
    current_desc_lines = []
    
    # Section headers that indicate parameter list
    param_headers = {'args:', 'arguments:', 'parameters:', 'params:', 
                     'raises:', 'exceptions:', 'except:',
                     'returns:', 'yields:', 'attributes:'}
    
    for line in lines:
        stripped = line.strip().lower()
        
        # Check for section header
        if stripped in param_headers:
            # Save previous parameter
            if current_param and current_desc_lines:
                params[current_param] = ' '.join(current_desc_lines).strip()
            
            # Determine if this is a params section
            if stripped in ('args:', 'arguments:', 'parameters:', 'params:'):
                in_params_section = True
                current_param = None
                current_desc_lines = []
            else:
                in_params_section = False
            continue
        
        # If in params section, look for parameter definitions
        if in_params_section:
            # Match "param_name: description" or "param_name (type): description"
            match = re.match(r'^\s+(\w[\w\s]*?)\s*(?:\(.*?\))?\s*:\s*(.+)$', line)
            if match:
                # Save previous parameter
                if current_param and current_desc_lines:
                    params[current_param] = ' '.join(current_desc_lines).strip()
                
                current_param = match.group(1).strip()
                current_desc_lines = [match.group(2)]
            elif current_param and (line.startswith('    ') or line.startswith('\t')):
                # Continuation line
                if stripped:
                    current_desc_lines.append(stripped)
    
    # Save last parameter
    if current_param and current_desc_lines:
        params[current_param] = ' '.join(current_desc_lines).strip()
    
    return params


def _parse_numpy_style(docstring):
    """Parse NumPy-style docstring parameters.
    
    Format:
        Parameters
        ----------
        param_name : type
            Description here
    """
    params = {}
    lines = docstring.split('\n')
    in_params_section = False
    current_param = None
    current_desc_lines = []
    
    # Look for Parameters section with underline
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip().lower()
        
        # Check for section header with underline pattern
        if stripped in ('parameters', 'params', 'arguments', 'args'):
            # Check if next line is underline (dashes)
            if i + 1 < len(lines) and re.match(r'^[-=]+$', lines[i + 1].strip()):
                # Save previous parameter
                if current_param and current_desc_lines:
                    params[current_param] = ' '.join(current_desc_lines).strip()
                
                in_params_section = True
                current_param = None
                current_desc_lines = []
                i += 2  # Skip header and underline
                continue
        
        # Check for end of section (new section header with underline)
        if in_params_section and stripped and not line.startswith(' '):
            # Check if this looks like a new section header
            if i + 1 < len(lines) and re.match(r'^[-=~]+$', lines[i + 1].strip()):
                # New section started
                if current_param and current_desc_lines:
                    params[current_param] = ' '.join(current_desc_lines).strip()
                in_params_section = False
                i += 1
                continue
        
        if in_params_section:
            # Match parameter definition: "param_name : type" or just "param_name"
            match = re.match(r'^(\w[\w\s]*?)\s*:\s*(.*)$', line)
            if match and not line.startswith('    '):
                # Save previous parameter
                if current_param and current_desc_lines:
                    params[current_param] = ' '.join(current_desc_lines).strip()
                
                current_param = match.group(1).strip()
                current_desc_lines = []
            elif current_param and (line.startswith('    ') or line.startswith('\t')):
                # Description line (indented)
                if stripped:
                    current_desc_lines.append(stripped)
        
        i += 1
    
    # Save last parameter
    if current_param and current_desc_lines:
        params[current_param] = ' '.join(current_desc_lines).strip()
    
    return params


def _parse_sphinx_style(docstring):
    """Parse Sphinx/reST-style docstring parameters.
    
    Format:
        :param param_name: Description
        :arg param_name: Description
        :param type param_name: Description
    """
    params = {}
    
    # Pattern for :param name: or :arg name: or :param type name:
    pattern = r':(?:param|arg|argument|key|kwarg)\s+(?:(\w+)\s+)?(\w+)\s*:\s*(.+?)(?=\n\s*:|$)'
    
    matches = re.finditer(pattern, docstring, re.DOTALL)
    for match in matches:
        # type_name = match.group(1)  # Optional type
        param_name = match.group(2)
        description = match.group(3).strip()
        # Clean up multi-line descriptions
        description = re.sub(r'\s+', ' ', description)
        params[param_name] = description
    
    return params


def parse_docstring(docstring):
    """Parse docstring into description, parameters, and returns sections.
    
    Supports Google, NumPy, and Sphinx/reST styles. Tries parsers in order
    of specificity and returns the first successful result.
    
    Args:
        docstring: The docstring text to parse
        
    Returns:
        dict: {
            'description': str - Functional description (without params)
            'params': dict - Parameter name to description mapping
            'param_types': dict - Parameter name to JSON Schema type mapping
            'returns': str - Return value description
        }
    """
    if not docstring:
        return {'description': '', 'params': {}, 'param_types': {}, 'returns': ''}
    
    cleaned = _clean_docstring(docstring)
    if not cleaned:
        return {'description': '', 'params': {}, 'param_types': {}, 'returns': ''}
    
    # Try parsers in order: Sphinx > Google > NumPy
    for parser in (_parse_sphinx_complete, _parse_google_complete, _parse_numpy_complete):
        result = parser(cleaned)
        if result.get('params') or result.get("param_types") or result.get("returns"):
            return result
    
    # Fallback: use full docstring as description.
    return {
        'description': cleaned,
        'params': {},
        'param_types': {},
        'returns': ''
    }


def _parse_sphinx_complete(docstring):
    """Parse Sphinx-style docstring completely."""
    result = {
        'description': '',
        'params': {},
        'param_types': {},  # Extract :type: directives and convert to JSON Schema types
        'returns': ''
    }
    
    lines = docstring.split('\n')
    desc_lines = []
    in_returns = False
    in_params = False  # Track if we've entered params section
    current_param = None
    current_param_desc_lines = []
    
    def save_current_param():
        nonlocal current_param, current_param_desc_lines
        if current_param and current_param_desc_lines:
            # Join multi-line param description with space
            result['params'][current_param] = ' '.join(current_param_desc_lines).strip()
            current_param = None
            current_param_desc_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check for :type: directive (extract and convert type info)
        type_match = re.match(r':type\s+(\w+)\s*:\s*(.+)', stripped)
        if type_match:
            param_name = type_match.group(1)
            type_str = type_match.group(2).strip()
            # Convert to JSON Schema type immediately using centralized utility
            result['param_types'][param_name] = docstring_type_to_json_type(type_str)
            continue
        
        # Check for :returns: or :return:
        if stripped.startswith(':returns:') or stripped.startswith(':return:'):
            save_current_param()  # Save any pending param
            in_returns = True
            in_params = True  # Also stop collecting description
            result['returns'] = stripped.split(':', 2)[-1].strip()
            continue
        
        # Check for :param: or :arg:
        if stripped.startswith(':param ') or stripped.startswith(':arg '):
            save_current_param()  # Save previous param
            in_params = True  # Stop collecting description
            match = re.match(r':(?:param|arg)\s+(?:\w+\s+)?(\w+)\s*:\s*(.*)', stripped)
            if match:
                current_param = match.group(1)
                param_desc = match.group(2).strip()
                if param_desc:
                    current_param_desc_lines = [param_desc]
                else:
                    current_param_desc_lines = []
            continue
        
        # Skip other directives
        if stripped.startswith(':'):
            continue
        
        # If in params section and line is indented, it's a continuation
        if in_params and not in_returns and (line.startswith('    ') or line.startswith('\t')):
            if current_param and stripped:
                current_param_desc_lines.append(stripped)
            continue
        
        # Collect description only before params/returns sections
        if not in_returns and not in_params and stripped:
            desc_lines.append(line)
    
    save_current_param()  # Save last param
    
    if desc_lines:
        result['description'] = ' '.join(line.strip() for line in desc_lines).strip()
    
    return result


def _parse_google_complete(docstring):
    """Parse Google-style docstring completely."""
    result = {
        'description': '',
        'params': {},
        'returns': ''
    }
    
    lines = docstring.split('\n')
    desc_lines = []
    current_section = 'description'  # description, params, returns
    current_param = None
    current_desc_lines = []
    
    section_headers = {
        'args:': 'params',
        'arguments:': 'params',
        'parameters:': 'params',
        'params:': 'params',
        'returns:': 'returns',
        'return:': 'returns',
        'raises:': None,  # Ignore raises section
        'exceptions:': None,
        'except:': None,
        'yields:': None,
        'attributes:': None,
        'note:': None,
        'notes:': None,
        'example:': None,
        'examples:': None,
    }
    
    def save_current_param():
        nonlocal current_param, current_desc_lines
        if current_param and current_desc_lines:
            result['params'][current_param] = ' '.join(current_desc_lines).strip()
            current_param = None
            current_desc_lines = []
    
    for line in lines:
        stripped_lower = line.strip().lower()
        
        # Check for section header
        if stripped_lower in section_headers:
            save_current_param()
            current_section = section_headers[stripped_lower]
            if current_section is None:
                current_section = 'ignore'
            continue
        
        # Process based on current section
        if current_section == 'params':
            # Match "param_name: description" or "param_name (type): description"
            match = re.match(r'^\s+(\w[\w\s]*?)\s*(?:\(.*?\))?\s*:\s*(.+)$', line)
            if match:
                save_current_param()
                current_param = match.group(1).strip()
                current_desc_lines = [match.group(2)]
            elif current_param and (line.startswith('    ') or line.startswith('\t')):
                if stripped_lower:
                    current_desc_lines.append(stripped_lower)
        
        elif current_section == 'returns':
            if stripped_lower:
                if result['returns']:
                    result['returns'] += ' ' + stripped_lower
                else:
                    result['returns'] = stripped_lower
        
        elif current_section == 'description':
            if stripped_lower:
                desc_lines.append(line)
    
    save_current_param()
    
    if desc_lines:
        result['description'] = ' '.join(line.strip() for line in desc_lines).strip()
    
    return result


def _parse_numpy_complete(docstring):
    """Parse NumPy-style docstring completely."""
    result = {
        'description': '',
        'params': {},
        'returns': ''
    }
    
    lines = docstring.split('\n')
    desc_lines = []
    current_section = 'description'
    current_param = None
    current_desc_lines = []
    i = 0
    
    def save_current_param():
        nonlocal current_param, current_desc_lines
        if current_param and current_desc_lines:
            result['params'][current_param] = ' '.join(current_desc_lines).strip()
            current_param = None
            current_desc_lines = []
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip().lower()
        
        # Check for section header with underline
        if stripped in ('parameters', 'params', 'arguments', 'args'):
            if i + 1 < len(lines) and re.match(r'^[-=]+$', lines[i + 1].strip()):
                save_current_param()
                current_section = 'params'
                i += 2
                continue
        
        elif stripped in ('returns', 'return'):
            if i + 1 < len(lines) and re.match(r'^[-=]+$', lines[i + 1].strip()):
                save_current_param()
                current_section = 'returns'
                i += 2
                continue
        
        # Check for end of section
        if current_section != 'description' and stripped and not line.startswith(' '):
            if i + 1 < len(lines) and re.match(r'^[-=~]+$', lines[i + 1].strip()):
                save_current_param()
                current_section = 'ignore'
                i += 2
                continue
        
        if current_section == 'params':
            match = re.match(r'^(\w[\w\s]*?)\s*:\s*(.*)$', line)
            if match and not line.startswith('    '):
                save_current_param()
                current_param = match.group(1).strip()
                current_desc_lines = []
            elif current_param and (line.startswith('    ') or line.startswith('\t')):
                if stripped:
                    current_desc_lines.append(stripped)
        
        elif current_section == 'returns':
            if stripped:
                if result['returns']:
                    result['returns'] += ' ' + stripped
                else:
                    result['returns'] = stripped
        
        elif current_section == 'description':
            if stripped:
                desc_lines.append(line)
        
        i += 1
    
    save_current_param()
    
    if desc_lines:
        result['description'] = ' '.join(line.strip() for line in desc_lines).strip()
    
    return result


def parse_docstring_params(docstring):
    """Parse parameter descriptions from docstring (legacy compatibility).
    
    This is a wrapper around parse_docstring() for backward compatibility.
    
    Args:
        docstring: The docstring text to parse
        
    Returns:
        dict: Mapping of parameter names to their descriptions
    """
    return parse_docstring(docstring)['params']


def extract_tool_description(docstring):
    """Extract concise tool description from docstring (legacy compatibility).
    
    This is a wrapper around parse_docstring() for backward compatibility.
    
    Args:
        docstring: The full docstring text
        
    Returns:
        str: Concise description without parameter details
    """
    result = parse_docstring(docstring)
    return result['description'] if result['description'] else "Odoo Tool"

