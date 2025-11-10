# Error Reporting Improvements

## Overview

The Tyco Python parser has been enhanced with modern, Python 3.10+ style error formatting that provides better context and precise error location information.

## Key Changes

### 1. Cached Source Lines
- **Before**: Error location tracking relied on storing `fragment` attributes on every parsed object
- **After**: The full source is cached once in `TycoLexer.source_lines` and referenced when needed

### 2. Modern Error Formatting
Error messages now follow the Python 3.10+ format with:
- File path with line and column numbers
- Source code context showing the problematic line
- Caret (^) pointer indicating the exact error location

### Example Error Output

**Before:**
```
test.tyco:1:13 - Must provide a value when setting globals
    string name:
```

**After:**
```
  File "test.tyco", line 1:13
    string name:
                ^
TycoParseError: Must provide a value when setting globals
```

## Implementation Details

### Updated Components

1. **TycoParseError Class** (`lines 38-88`)
   - Accepts `source_lines` parameter for cached source
   - `__str__()` method formats errors with Python-style output
   - Handles tab characters properly when positioning the caret

2. **_raise_parse_error Function** (`lines 252-270`)
   - Supports both legacy fragment-based errors (backward compatible)
   - Accepts direct row/col/source_lines parameters for new approach
   - Extracts location info from SourceString fragments automatically

3. **TycoLexer Class** (`lines 273-633`)
   - Caches source lines in `self.source_lines` during initialization
   - `_parse_error()` method passes source_lines to error raising
   - All parsing errors include full source context

4. **TycoContext Class** (`lines 634-826`)
   - New `_get_source_lines()` helper method
   - Retrieves cached source from path cache for multi-file errors
   - Enables error formatting even for included files

5. **Error Methods in Data Classes**
   - `TycoInstance._error()` - passes context source_lines
   - `TycoReference._error()` - passes context source_lines
   - `TycoArray._error()` - passes context source_lines
   - `TycoValue._error()` - passes context source_lines

### Backward Compatibility

The changes maintain full backward compatibility:
- Fragment attributes are still stored on objects (used as fallback)
- `_raise_parse_error()` accepts both old and new calling conventions
- All 40 existing tests pass without modification

## Benefits

1. **Better User Experience**: Clearer, more informative error messages
2. **Familiar Format**: Matches Python's built-in error display
3. **Reduced Memory**: Source cached once instead of duplicated in fragments
4. **Precise Location**: Caret points exactly to the error position
5. **Tab Handling**: Correctly accounts for tab characters in positioning

## Testing

All error reporting improvements have been validated:
- ✅ 40 existing pytest tests pass
- ✅ Parse-time errors show correct line/column
- ✅ Render-time errors show correct source context
- ✅ Multi-file errors work with includes
- ✅ Tab characters handled properly in caret positioning

## Future Enhancements

Possible future improvements:
- Show multiple lines of context (before/after the error)
- Color coding for terminal output
- Suggestions for common mistakes
- Multiple error reporting in one pass
