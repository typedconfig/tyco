# Tyco Parser Implementation - Python

This repository contains the **Python implementation** of the Tyco configuration language parser. It is part of a multi-language project where the same parser specification is implemented across Python, JavaScript, Rust, Go, and potentially other languages.

## 🎯 Project Context

### What is Tyco?
Tyco is a modern, type-safe configuration language designed for clarity and flexibility. It supports:
- Strong type annotations (str, int, float, bool, datetime, etc.)
- Struct definitions with primary keys
- Template support for reusability
- References between configuration values
- Arrays and nested structures

### Multi-Language Implementation
This Python implementation must maintain **identical parsing behavior** with other language implementations:
- All implementations parse the same `.tyco` test files
- All implementations produce the same output for identical inputs
- Test files in `tyco/tests/inputs/` are canonical examples
- Expected outputs in `tyco/tests/expected/` define correct behavior

## 📋 Core Parsing Rules

When implementing or modifying parser logic, always ensure:

1. **Type Parsing**: Support str, int, float, bool, datetime, date, time, timedelta
2. **Number Formats**: Handle decimal, hexadecimal (0x), octal (0o), binary (0b), scientific notation
3. **String Formats**: 
   - Unquoted strings (single words)
   - Quoted strings with escape sequences
   - Multi-line strings with proper whitespace handling
4. **Struct Definitions**: 
   - Primary key fields marked with `*`
   - Instance data follows field definitions
   - Comma-separated values
5. **References**: `@variable_name` and `@Struct.field` syntax
6. **Templates**: Reusable configuration blocks
7. **Arrays**: `[item1, item2, item3]` syntax
8. **Nullable Types**: `?str`, `?int`, etc. allowing null/None values
9. **Default Values**: Field definitions can include defaults

## 🧪 Test-Driven Development

The test suite in `tyco/tests/` is the **source of truth** for parser behavior:

### Test Files (inputs/)
- `basic_types.tyco` - Core type annotations
- `number_formats.tyco` - All number format variations
- `quoted_strings.tyco` - String escaping and quotes
- `arrays.tyco` - Array syntax
- `references.tyco` - Variable and field references
- `templates.tyco` - Template definitions
- `nullable.tyco` - Optional/nullable types
- `datetime_types.tyco` - Date/time parsing
- `defaults.tyco` - Default value handling
- `edge_cases.tyco` - Corner cases and special scenarios

### Expected Outputs (expected/)
Each test file has a corresponding `.json` file with the expected parsed output.

## 🤖 AI Assistant Guidelines

When helping with this codebase:

1. **Refer to Test Files**: Use test files as canonical examples of Tyco syntax
2. **Maintain Consistency**: Changes must not break existing tests
3. **Cross-Language Awareness**: Consider how changes affect other implementations
4. **Test-First**: When adding features, start with test cases
5. **Parser Structure**: 
   - Lexical analysis in early sections
   - Parsing logic follows
   - AST/object construction at the end
6. **Error Messages**: Should be clear and point to line numbers when possible

## 🔧 Common Tasks

### Running Tests
```bash
pytest -v
pytest tyco/tests/test_parser.py::test_specific_case
```

### Adding a New Feature
1. Add test case to appropriate file in `tests/inputs/`
2. Add expected output to `tests/expected/`
3. Update parser logic
4. Verify all tests pass
5. Document in README if it's a user-facing feature

### Debugging Parser Issues
- Use test files to isolate the issue
- Check expected output for correct behavior
- Compare with other language implementations if needed
- Test edge cases

## 📚 Language Specification

For authoritative language specification details, refer to:
- Official documentation at https://typedconfig.io
- Test suite (this is the executable specification)
- Cross-reference with other language implementations when unclear

## 🚨 Important Notes

- **DO NOT** modify test files without updating all language implementations
- **ALWAYS** run full test suite before committing
- **ENSURE** parser behavior matches expected JSON outputs exactly
- **CONSIDER** impact on other language implementations when making spec changes

---

This implementation should remain compatible with the shared test suite and maintain consistent behavior with sibling implementations in other languages.
