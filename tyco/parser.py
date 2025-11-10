#!/usr/bin/env python3

import os
import re
import sys
import enum
import types
import string
import decimal
import pathlib
import datetime
import itertools
import importlib
import collections


__all__ = ['Struct', 'load', 'loads', 'TycoParseError']


ASCII_CTRL = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))
ILLEGAL_STR_CHARS           = ASCII_CTRL - frozenset("\t")
ILLEGAL_STR_CHARS_MULTILINE = ASCII_CTRL - frozenset("\r\n\t")
BASIC_STR_ESCAPE_REPLACEMENTS = {
        r"\b": "\u0008",  # backspace
        r"\t": "\u0009",  # tab
        r"\n": "\u000A",  # linefeed
        r"\f": "\u000C",  # form feed
        r"\r": "\u000D",  # carriage return
        r'\"': "\u0022",  # quote
        r"\\": "\u005C",  # backslash
    }
BASIC_STR_ESCAPE_REGEX = rf"(?:{'|'.join(re.escape(k) for k in BASIC_STR_ESCAPE_REPLACEMENTS)})"
UNICODE_REGEX = r'\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})'
HEXDIGIT_CHARS = frozenset(string.hexdigits)
EOL_REGEX = r'\s*(?:#.*)?' + re.escape(os.linesep)


class TycoParseError(Exception):

    def __init__(self, message, *, source=None, row=None, col=None, source_lines=None):
        super().__init__(message)
        self.message = message
        self.source = source
        self.row = row
        self.col = col
        self.source_lines = source_lines

    def __str__(self):
        parts = []
        
        # Build location string
        location_parts = []
        if self.source:
            location_parts.append(f'File "{self.source}"')
        if self.row is not None:
            if self.col is not None:
                location_parts[-1] += f', line {self.row}, column {self.col}:'
            else:
                location_parts[-1] += f', line {self.row}:'
        
        if location_parts:
            parts.append('  ' + location_parts[0])
        
        # Add source line with context if available
        if self.source_lines and self.row is not None:
            # Show the problematic line
            line_idx = self.row - 1
            if 0 <= line_idx < len(self.source_lines):
                line = self.source_lines[line_idx].rstrip('\n')
                parts.append(f'    {line}')
                
                # Add caret/arrow pointer if we have column info
                if self.col is not None and self.col > 0:
                    # Calculate visual position accounting for tabs
                    visual_col = 0
                    for i, ch in enumerate(line):
                        if i >= self.col - 1:
                            break
                        if ch == '\t':
                            visual_col = (visual_col // 8 + 1) * 8  # Tab to next 8-char boundary
                        else:
                            visual_col += 1
                    
                    # Build the pointer line
                    pointer = ' ' * (4 + visual_col) + '^'
                    parts.append(pointer)
        
        # Add the error message
        parts.append(f'{self.__class__.__name__}: {self.message}')
        
        return '\n'.join(parts)


class SourceString(str):

    __slots__ = ('row', 'col', 'source')

    def __new__(cls, value='', *, row=1, col=1, source=None):
        obj = super().__new__(cls, value)
        obj.row = row
        obj.col = col
        obj.source = source
        return obj

    def _location_for_offset(self, offset):
        length = len(self)
        if offset < 0:
            offset += length
        offset = max(0, min(length, offset))
        prefix = str.__getitem__(self, slice(0, offset))
        row = self.row
        col = self.col
        for ch in prefix:
            if ch == '\n':
                row += 1
                col = 1
            else:
                col += 1
        return row, col

    def advance(self, offset):
        return self._location_for_offset(offset)

    def _wrap(self, value, offset):
        if isinstance(value, SourceString):
            return value
        row, col = self._location_for_offset(offset)
        return SourceString(value, row=row, col=col, source=self.source)

    def __getitem__(self, key):
        result = super().__getitem__(key)
        if isinstance(result, SourceString):
            return result
        if isinstance(key, slice):
            start = key.start or 0
            if start < 0:
                start += len(self)
            return self._wrap(result, start)
        if isinstance(key, int):
            idx = key if key >= 0 else len(self) + key
            return self._wrap(result, idx)
        return result

    def __add__(self, other):
        value = super().__add__(other)
        if isinstance(value, SourceString):
            return value
        return SourceString(value, row=self.row, col=self.col, source=self.source)

    def __radd__(self, other):
        value = super().__radd__(other)
        if isinstance(other, SourceString):
            return SourceString(value, row=other.row, col=other.col, source=other.source)
        return SourceString(value, row=self.row, col=self.col, source=self.source)

    def lstrip(self, chars=None):
        stripped = super().lstrip(chars)
        if stripped == str(self):
            return self
        removed = len(self) - len(stripped)
        row, col = self._location_for_offset(removed)
        return SourceString(stripped, row=row, col=col, source=self.source)

    def rstrip(self, chars=None):
        stripped = super().rstrip(chars)
        if stripped == str(self):
            return self
        return SourceString(stripped, row=self.row, col=self.col, source=self.source)

    def split(self, sep=None, maxsplit=-1):
        if sep is None:
            parts = super().split(sep, maxsplit)
            return [SourceString(part, row=self.row, col=self.col, source=self.source) for part in parts]
        sep_len = len(sep)
        if sep_len == 0:
            raise ValueError('empty separator')
        value = str(self)
        start = 0
        splits = 0
        result = []
        while True:
            if maxsplit != -1 and splits >= maxsplit:
                break
            idx = value.find(sep, start)
            if idx == -1:
                break
            result.append(self._wrap(value[start:idx], start))
            start = idx + sep_len
            splits += 1
        result.append(self._wrap(value[start:], start))
        return result

    def strip(self, chars=None):
        return self.lstrip(chars).rstrip(chars)

def sub_escape_sequences(content, basic_string=False):

    def repl(match):
        return BASIC_STR_ESCAPE_REPLACEMENTS[match.group(0)]

    escaped = re.sub(BASIC_STR_ESCAPE_REGEX, repl, content)

    def repl(match):
        hex_str = match.group(1) or match.group(2)
        return chr(int(hex_str, 16))

    escaped = re.sub(UNICODE_REGEX, repl, escaped)
    escaped = re.sub(r'/\s*\r?\n\s*', '', escaped)        # remove escaped newline + trailing whitespace
    return escaped


def strip_comments(line):
    content, *comments = line.split('#', maxsplit=1)
    if comments:
        comment = comments[0].rstrip(os.linesep)
        invalid = set(comment) & ILLEGAL_STR_CHARS
        if invalid:
            raise TycoParseError(
                f'Invalid characters in comments: {invalid}',
                source=getattr(comment, 'source', None),
                row=getattr(comment, 'row', None),
                col=getattr(comment, 'col', None),
                line=str(comment),
            )
    return content.rstrip()


def is_whitespace(content):
    return re.match(r'\s*$', str(content))


def cached_property(func):
    @property
    def wrapper(self):
        cache_name = f'_{func.__name__}_cache'
        if not hasattr(self, cache_name):
            setattr(self, cache_name, func(self))
        return getattr(self, cache_name)
    return wrapper


def _coerce_lines(lines, *, source=None, start_row=1):
    coerced = []
    for idx, line in enumerate(lines):
        if isinstance(line, SourceString):
            coerced.append(line)
        else:
            coerced.append(SourceString(line, row=start_row + idx, col=1, source=source))
    return coerced


def _raise_parse_error(message, fragment=None, *, source=None, row=None, col=None, source_lines=None):
    """
    Raise a TycoParseError with source location and cached source lines.
    
    Can be called with either:
    - fragment (legacy): SourceString or str with error location
    - row/col/source_lines (new): Direct location with cached source for better formatting
    """
    if fragment:
        # Legacy path: extract from fragment
        if isinstance(fragment, SourceString):
            source = fragment.source or source
            row = fragment.row
            col = fragment.col
            source_lines = getattr(fragment, 'source_lines', None) or source_lines
        # For plain strings, we don't have location info
    
    raise TycoParseError(message, source=source, row=row, col=col, source_lines=source_lines)


class TycoLexer:

    ire = r'((?!\d)\w+)'            # regex to match identifiers
    GLOBAL_SCHEMA_REGEX = rf'([?])?{ire}(\[\])?\s+{ire}\s*:'
    STRUCT_BLOCK_REGEX  = rf'^{ire}:'
    STRUCT_SCHEMA_REGEX = rf'^\s+([*?])?{ire}(\[\])?\s+{ire}\s*:'
    STRUCT_DEFAULTS_REGEX = rf'\s+{ire}\s*:'
    STRUCT_INSTANCE_REGEX = r'\s+-'

    @classmethod
    def from_path(cls, context, path):
        if path not in context._path_cache:
            if not os.path.isfile(path):
                raise TycoParseError(f'Can only load path if it is a regular file: {path}', source=path)
            base_filename = path
            if base_filename.endswith('.tyco'):
                base_filename = base_filename[:-5]
            module_path = f'{base_filename}.py'
            if os.path.exists(module_path):
                try:
                    module_name = os.path.basename(base_filename).replace('-', '_')
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                except Exception:
                    # Ignore import errors in validation modules
                    pass
            with open(path) as f:
                lines = list(f.readlines())
            lines = _coerce_lines(lines, source=path)
            lexer = cls(context, lines, path)
            lexer.process()
            context._path_cache[path] = lexer
        return context._path_cache[path]

    def __init__(self, context, lines, path=None):
        self.context = context
        self.lines = collections.deque(lines)
        self.path = path
        self.num_lines = len(lines)
        self.defaults = {}       # {type_name : {attr_name : TycoInstance|TycoValue|TycoArray|TycoReference}}
        self.source = path
        # Cache the full source as a list for error reporting
        self.source_lines = [str(line) for line in lines]

    def process(self):
        while self.lines:
            line = self.lines.popleft()
            if match := re.match(r'#include\s+(\S.*)$', line):
                path = match.groups()[0]
                if not os.path.isabs(path):
                    if self.path is None:
                        rel_dir = os.getcwd()
                    else:
                        rel_dir = os.path.dirname(self.path)
                    path = os.path.join(rel_dir, path)
                lexer = self.__class__.from_path(self.context, path)
                lexer.process()
                for type_name, attr_defaults in lexer.defaults.items():
                    if type_name in self.defaults:
                        raise TycoParseError(
                            f'Duplicate struct defaults for {type_name}',
                            source=path,
                        )
                    self.defaults[type_name] = attr_defaults.copy()
                continue
            if match := re.match(self.GLOBAL_SCHEMA_REGEX, line):
                self._load_global(line, match)
                continue
            elif match := re.match(self.STRUCT_BLOCK_REGEX, line):
                type_name = match.groups()[0]
                if type_name not in self.context._structs:
                    struct = self.context._add_struct(type_name)
                    self._load_schema(struct)
                struct = self.context._structs[type_name]
                self._load_local_defaults_and_instances(struct)
                continue
            elif not strip_comments(line):
                continue
            self._parse_error(line, 'Malformatted config file')

    def _load_global(self, line, match):
        options, type_name, array_flag, attr_name = match.groups()
        is_array = array_flag == '[]'
        is_nullable = options == '?'
        default_text = line.split(':', maxsplit=1)[1].lstrip()
        if not default_text:
            colon = line.find(':')
            self._parse_error(line, 'Must provide a value when setting globals', column_offset=colon + 1 if colon != -1 else 0)
        self.lines.appendleft(default_text)
        attr, delim = self._load_tyco_attr(attr_name=attr_name)
        attr.apply_schema_info(type_name=type_name, attr_name=attr_name, is_nullable=is_nullable, is_array=is_array)
        self.context._set_global_attr(attr_name, attr)

    def _load_schema(self, struct):
        if struct.type_name in self.defaults:
            raise TycoParseError(
                f'Duplicate schema definition for {struct.type_name}',
                source=self.path,
            )
        self.defaults[struct.type_name] = {}
        while True:
            if not self.lines:
                break
            content = strip_comments(self.lines[0])
            if not content:                 # blank lines or comments
                self.lines.popleft()
                continue
            if not (match := re.match(self.STRUCT_SCHEMA_REGEX, content)):
                if re.match(r'\s+\w+\s+\w+', content):
                    self._parse_error(content, 'Schema attribute missing trailing colon')
                break
            line = self.lines.popleft()
            options, type_name, array_flag, attr_name = match.groups()
            if attr_name in struct.attr_types:
                self._parse_error(line, f'Duplicate attribute {attr_name} found in {struct.type_name}')
            struct.attr_types[attr_name] = type_name
            if (is_array := array_flag == '[]'):
                struct.array_keys.add(attr_name)
            if options == '*':
                if is_array:
                    self._parse_error(line, 'Cannot set a primary key on an array')
                struct.primary_keys.append(attr_name)
            elif options == '?':
                struct.nullable_keys.add(attr_name)
            default_text = line.split(':', maxsplit=1)[1].lstrip()
            default_content = strip_comments(default_text)
            if default_content:
                self.lines.appendleft(default_text)
                attr, delim = self._load_tyco_attr(attr_name=attr_name)
                self.defaults[struct.type_name][attr_name] = attr

    def _load_local_defaults_and_instances(self, struct):
        while True:
            if not self.lines:
                break
            if self.lines[0].startswith('#include '):
                break
            content = strip_comments(self.lines[0])
            if not content:                 # blank lines or comments
                self.lines.popleft()
                continue
            if not self.lines[0][0].isspace():  # start of a new struct
                break
            if match := re.match(self.STRUCT_SCHEMA_REGEX, self.lines[0]):
                self._parse_error(self.lines[0], 'Cannot add schema attributes after initial construction')
            line = self.lines.popleft()
            if match := re.match(self.STRUCT_DEFAULTS_REGEX, line):
                attr_name = match.groups()[0]
                if attr_name not in struct.attr_types:
                    self._parse_error(line, f'Setting invalid default of {attr_name} for {struct}')
                default_text = line.split(':', maxsplit=1)[1].lstrip()
                if strip_comments(default_text):
                    self.lines.appendleft(default_text)
                    attr, delim = self._load_tyco_attr(attr_name=attr_name)
                    self.defaults[struct.type_name][attr_name] = attr
                else:
                    self.defaults[struct.type_name].pop(attr_name, None)          # if empty remove previous defaults
            elif match := re.match(self.STRUCT_INSTANCE_REGEX, line):
                self.lines.appendleft(line.split('-', maxsplit=1)[1].lstrip())
                inst_args = []
                while True:
                    if not self.lines:
                        break
                    inst_content = strip_comments(self.lines[0])
                    if not inst_content:
                        self.lines.popleft()
                        break
                    if inst_content == '\\':                # continues line to next line
                        self.lines.popleft()
                        if self.lines:
                            self.lines[0] = self.lines[0].lstrip()
                        continue
                    attr, delim = self._load_tyco_attr(good_delim=(',', os.linesep), pop_empty_lines=False)
                    inst_args.append(attr)
                struct.create_instance(inst_args, self.defaults[struct.type_name])

    def _parse_error(self, line, message, column_offset=0):
        """Raise a parse error with proper source location."""
        if isinstance(line, SourceString):
            _raise_parse_error(
                message,
                source=line.source or self.path,
                row=line.row,
                col=line.col + column_offset if line.col is not None else None,
                source_lines=self.source_lines
            )
        else:
            _raise_parse_error(message, source=self.path, source_lines=self.source_lines)

    def _load_tyco_attr(self, good_delim=(os.linesep,), bad_delim='', pop_empty_lines=True, attr_name=None):
        bad_delim = set(bad_delim) | set('()[],') - set(good_delim)
        if not self.lines:
            raise TycoParseError('Syntax error: no content found', source=self.path)
        if match := re.match(rf'{self.ire}\s*:\s*', self.lines[0]):     # need to exclude times w/ colons
            if attr_name is not None:
                self._parse_error(self.lines[0], f'Colon : found in content - enclose in quotes to prevent being used as a field name: {match.groups()[0]}', column_offset=match.start())
            attr_name = match.groups()[0]
            self.lines[0] = self.lines[0][match.span()[1]:]
            return self._load_tyco_attr(good_delim, bad_delim, pop_empty_lines, attr_name=attr_name)
        ch = self.lines[0][:1]
        if ch == '[':                                               # inline array
            opening_fragment = self.lines[0]
            self.lines[0] = self.lines[0][1:]
            content = self._load_array(']')
            attr = TycoArray(self.context, content)
            attr.fragment = opening_fragment
            attr.source = getattr(opening_fragment, 'source', None)
            delim = self._strip_next_delim(good_delim)
        elif match := re.match(r'(\w+)\(', self.lines[0]):           # inline instance/reference
            invocation_fragment = self.lines[0]
            type_name = match.groups()[0]
            self.lines[0] = self.lines[0][match.span()[1]:]
            inst_args = self._load_array(')')
            if type_name not in self.context._structs or self.context._structs[type_name].primary_keys:
                attr = TycoReference(self.context, inst_args, type_name)
                attr.fragment = invocation_fragment
            else:
                default_kwargs = self.defaults[type_name]
                attr = self.context._structs[type_name].create_inline_instance(inst_args, default_kwargs)
            delim = self._strip_next_delim(good_delim)
        elif ch in ('"', "'"):                                      # quoted string
            opening_fragment = self.lines[0]
            if (triple := ch*3) == self.lines[0][:3]:
                quoted_string = self._load_triple_string(triple, opening_fragment)
            else:
                quoted_string = self._load_single_string(ch, opening_fragment)
            attr = TycoValue(self.context, quoted_string)
            delim = self._strip_next_delim(good_delim)
        else:
            attr, delim = self._strip_next_attr_and_delim(good_delim, bad_delim)
        self.lines[0] = self.lines[0].lstrip(' \t')                 # do not strip off newlines
        if pop_empty_lines and not self.lines[0]:
            self.lines.popleft()
        attr.apply_schema_info(attr_name=attr_name)
        return attr, delim

    def _strip_next_delim(self, good_delim):
        delim_regex = '^' + '|'.join(re.escape(d) for d in good_delim)
        if not (match := re.match(delim_regex, self.lines[0])):
            if os.linesep in good_delim and not (content := strip_comments(self.lines[0])):
                delim = os.linesep                      # handles the case where we only have trailing comments
                self.lines[0] = ''
                return delim
            self._parse_error(self.lines[0], f'Should have found next delimiter {good_delim}')
        delim = match.group()
        start, end = match.span()
        self.lines[0] = self.lines[0][end:]
        return delim

    def _strip_next_attr_and_delim(self, good_delim, bad_delim):
        all_content = strip_comments(self.lines[0]) + os.linesep
        all_delim = list(good_delim) + list(bad_delim)
        delim_regex = '|'.join(re.escape(d) for d in all_delim)
        if not (match := re.search(delim_regex, all_content)):
            self._parse_error(self.lines[0], f'Should have found some delimiter {all_delim}')
        delim = match.group()
        if delim in bad_delim:
            self._parse_error(self.lines[0], f'Unexpected delimiter {delim!r}')
        start, end = match.span()
        text = all_content[:start]
        attr = TycoValue(self.context, text)
        self.lines[0] = self.lines[0][end:]                              # inline comments might be part of
        return attr, delim                                               # a string so dont use all_content

    def _load_array(self, closing_char):
        good_delims = (closing_char, ',')
        bad_delims  = ')' if closing_char == ']' else ']'
        array = []
        while True:
            if not self.lines:
                _raise_parse_error(
                    f"Unterminated list; expected '{closing_char}' before end of file",
                    source=self.path,
                )
            if not strip_comments(self.lines[0]):                       # can have newlines within the array
                self.lines.popleft()
                continue
            if self.lines[0].startswith(closing_char):                  # can happen with a trailing comma
                self.lines[0] = self.lines[0][1:]
                break
            attr, delim = self._load_tyco_attr(good_delims, bad_delims)
            array.append(attr)
            if delim == closing_char:
                break
        return array

    def _load_triple_string(self, triple, opening_fragment):
        is_literal = triple == "'''"
        start = 3
        all_contents = []
        while True:
            if not self.lines:
                _raise_parse_error(
                    'Unterminated triple-quoted string',
                    fragment=opening_fragment,
                    source=self.path,
                )
            line = self.lines.popleft()
            end = line.find(triple, start)
            if end != -1:
                end += 3                      # include the triple quote at end
                content = line[:end]
                remainder = line[end:]
                all_contents.append(content)
                break
            else:
                if not is_literal and line.endswith('\\' + os.linesep): # we strip trailing whitespace
                    line = line[:-(1+len(os.linesep))]                  # following a trailing slash
                    while self.lines:
                        self.lines[0] = self.lines[0].lstrip()
                        if not self.lines[0]:
                            self.lines.popleft()
                        else:
                            break
            all_contents.append(line)
            start = 0
        for i in range(2):                  # edge case: there can be a max of 2 additional quotes
            if remainder.startswith(triple[0]):
                all_contents[-1] += triple[0]
                remainder = remainder[1:]
            else:
                break
        final_content = ''.join(all_contents)
        if invalid := set(final_content) & ILLEGAL_STR_CHARS_MULTILINE:
            _raise_parse_error(
                f'Literal multiline strings must not contain control characters (found {invalid})',
                fragment=final_content,
                source=self.path,
            )
        self.lines.appendleft(remainder)
        return final_content

    def _load_single_string(self, ch, opening_fragment):
        is_literal = ch == "'"
        start = 1
        line = self.lines.popleft()
        while True:
            end = line.find(ch, start)
            if end == -1:
                _raise_parse_error(
                    f'Unterminated string literal (missing closing {ch})',
                    fragment=opening_fragment,
                    source=self.path,
                )
            if is_literal or line[end-1] != '\\':       # this is an escaped quote
                break
            start = end + 1
        end += 1                            # include quote at the end
        final_content = line[:end]
        remainder = line[end:]
        if invalid := set(final_content) & ILLEGAL_STR_CHARS:
            _raise_parse_error(
                f'Literal strings may not contain control characters (found {invalid})',
                fragment=final_content,
                source=self.path,
            )
        self.lines.appendleft(remainder)
        return final_content


class TycoContext:

    def __init__(self):
        self._path_cache = {}       # {path : TycoLexer()}
        self._structs    = {}       # {type_name : TycoStruct()}
        self._globals    = {}       # {attr_name : TycoValue|TycoInstance|TycoArray|TycoReference}

    def _get_source_lines(self, source_path):
        """Get cached source lines for a given path, if available."""
        if source_path in self._path_cache:
            return self._path_cache[source_path].source_lines
        return None

    def _set_global_attr(self, attr_name, attr):
        if attr_name in self._globals:
            fragment = getattr(attr, 'fragment', None)
            source_lines = self._get_source_lines(getattr(fragment, 'source', None)) if fragment else None
            _raise_parse_error(
                f"Global attribute '{attr_name}' is defined more than once",
                fragment=fragment or attr_name,
                source=getattr(attr, 'source', None),
                source_lines=source_lines,
            )
        self._globals[attr_name] = attr

    def _add_struct(self, type_name):
        self._structs[type_name] = struct = TycoStruct(self, type_name)
        return struct

    def _render_content(self):
        self._set_parents()
        self._render_base_content()
        self._load_primary_keys()
        self._render_references()
        self._render_templates()

    def _set_parents(self):
        for attr_name, attr in self._globals.items():
            attr.set_parent(self._globals)
        for struct in self._structs.values():
            for inst in struct.instances:
                inst.set_parent()

    def _render_base_content(self):
        for attr_name, attr in self._globals.items():
            attr.render_base_content()
        for struct in self._structs.values():
            for inst in struct.instances:
                inst.render_base_content()

    def _load_primary_keys(self):                          # primary keys can only be base types w/o templating
        for struct in self._structs.values():
            struct.load_primary_keys()

    def _render_references(self):
        for attr_name, attr in self._globals.items():
            attr.render_references()
        for struct in self._structs.values():
            for inst in struct.instances:
                inst.render_references()

    def _render_templates(self):
        for attr_name, attr in self._globals.items():
            attr.render_templates()
        for struct in self._structs.values():
            for inst in struct.instances:
                inst.render_templates()

    def get_globals(self):
        return Struct(**{a : i.get_object() for a, i in self._globals.items()})

    def get_objects(self):
        objects = {}
        for type_name, struct in self._structs.items():
            objects[type_name] = [i.get_object() for i in struct.instances]
        return objects

    def to_json(self):
        json_content = {}
        for attr_name, attr in self._globals.items():
            json_content[attr_name] = attr.to_json()
        for type_name, struct in self._structs.items():
            if not struct.primary_keys:                     # we don't serialize inline instances
                continue
            json_content[type_name] = struct_content = []
            for instance in struct.instances:
                struct_content.append(instance.to_json())
        return json_content


class TycoStruct:

    def __init__(self, context, type_name):
        self.context = context
        self.type_name = type_name
        self.attr_types = collections.OrderedDict()     # {attr_name : type_name}
        self.primary_keys = []                          # [attr_name,...]
        self.nullable_keys = set()                      # {attr_name,...}
        self.array_keys = set()                         # {attr_name,...}
        self.instances = []                             # [TycoInstance(),...]
        self.mapped_instances = {}                      # {primary_keys : TycoInstance}

    @cached_property
    def attr_names(self):
        return list(self.attr_types)

    def create_instance(self, inst_args, default_kwargs):
        inst = self.create_inline_instance(inst_args, default_kwargs)
        self.instances.append(inst)

    def create_inline_instance(self, inst_args, default_kwargs):
        inst_kwargs = {}
        kwargs_only = False
        for i, attr in enumerate(inst_args):
            if not attr.attr_name:
                if kwargs_only:
                    attr._error(
                        f"Positional arguments for '{self.type_name}' must appear before keyed arguments"
                    )
                attr.attr_name = self.attr_names[i]
            else:
                kwargs_only = True
            inst_kwargs[attr.attr_name] = attr
        complete_kwargs = self._resolve_complete_kwargs(inst_kwargs, default_kwargs)
        instance = TycoInstance(self.context, self.type_name, complete_kwargs)
        if inst_args:
            instance.fragment = getattr(inst_args[0], 'fragment', None)
        return instance

    def load_primary_keys(self):
        if not self.primary_keys:
            return
        for inst in self.instances:
            key = tuple(getattr(inst, k).rendered for k in self.primary_keys)
            if key in self.mapped_instances:
                primary_attr = getattr(inst, self.primary_keys[0])
                primary_attr._error(
                    f"{self.type_name} with primary key {key} already exists"
                )
            self.mapped_instances[key] = inst

    def load_reference(self, inst_args):
        inst_kwargs = {}
        kwargs_only = False
        for i, attr in enumerate(inst_args):
            if not attr.attr_name:
                if kwargs_only:
                    attr._error(
                        f"Positional reference arguments for '{self.type_name}' must appear before keyed arguments"
                    )
                attr_name = self.primary_keys[i]
            else:
                attr_name = attr.attr_name
                kwargs_only = True
            type_name = self.attr_types[attr_name]
            is_nullable = attr_name in self.nullable_keys
            is_array    = attr_name in self.array_keys
            attr.apply_schema_info(type_name=type_name, attr_name=attr_name, is_nullable=is_nullable, is_array=is_array)
            attr.render_base_content()
            inst_kwargs[attr_name] = attr
        key = tuple(inst_kwargs[attr_name].rendered for attr_name in self.primary_keys)
        if key not in self.mapped_instances:
            fragment = None
            if self.primary_keys:
                fragment = inst_kwargs[self.primary_keys[0]].fragment
            _raise_parse_error(
                f"{self.type_name} with primary key {key} was referenced before it was defined",
                fragment=fragment,
                source=self.context._path_cache and list(self.context._path_cache)[-1],
            )
        return self.mapped_instances[key]

    def _resolve_complete_kwargs(self, inst_kwargs, default_kwargs):
        complete_kwargs = {}
        for attr_name in self.attr_types:
            if attr_name in inst_kwargs:
                complete_kwargs[attr_name] = inst_kwargs[attr_name]
            elif attr_name in default_kwargs:
                val = default_kwargs[attr_name]
                if isinstance(val, list):
                    complete_kwargs[attr_name] = [v.make_copy() for v in val]
                else:
                    complete_kwargs[attr_name] = val.make_copy()
            else:
                _raise_parse_error(
                    f"Invalid attribute {attr_name} for struct '{self.type_name}': "
                    f"value is required and no default is defined"
                )
        for attr_name, attr in complete_kwargs.items():
            type_name = self.attr_types[attr_name]
            is_nullable = attr_name in self.nullable_keys
            is_array    = attr_name in self.array_keys
            attr.apply_schema_info(type_name=type_name, attr_name=attr_name, is_nullable=is_nullable, is_array=is_array)
        return complete_kwargs

    def __str__(self):
        return f'TycoStruct({self.type_name})'

    def __repr__(self):
        return self.__str__()


class TycoInstance:

    def __init__(self, context, type_name, inst_kwargs):
        self.context = context
        self.type_name = type_name
        self.inst_kwargs = inst_kwargs      # {attr_name : TycoValue|TycoInstance|TycoArray|TycoReference}
        self.attr_name   = None               # set later
        self.is_nullable = None               # set later
        self.is_array    = None               # set later
        self.parent      = None               # set later
        self._object = None
        self.fragment = None

    def make_copy(self):
        inst_kwargs = {a : i.make_copy() for a, i in self.inst_kwargs.items()}
        inst = self.__class__(self.context, self.type_name, inst_kwargs)
        inst.fragment = self.fragment
        return inst

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            if attr == 'type_name' and self.type_name != val:
                fragment = self.fragment
                source_lines = self.context._get_source_lines(getattr(fragment, 'source', None)) if fragment else None
                _raise_parse_error(
                    f"Field '{self.attr_name}' expects an instance of '{val}', but '{self.type_name}' was provided",
                    fragment=fragment,
                    source=getattr(fragment, 'source', None),
                    source_lines=source_lines,
                )
            setattr(self, attr, val)
        if self.is_array is True:
            fragment = self.fragment
            source_lines = self.context._get_source_lines(getattr(fragment, 'source', None)) if fragment else None
            _raise_parse_error(
                f"Field '{self.attr_name}' is declared as a list, but an object was provided",
                fragment=fragment,
                source=getattr(fragment, 'source', None),
                source_lines=source_lines,
            )

    def set_parent(self, parent=None):
        self.parent = parent
        for i in self.inst_kwargs.values():
            i.set_parent(self)

    def render_base_content(self):
        for i in self.inst_kwargs.values():
            i.render_base_content()

    def render_references(self):
        for i in self.inst_kwargs.values():
            i.render_references()

    def render_templates(self):
        for i in self.inst_kwargs.values():
            i.render_templates()

    @property
    def rendered(self):
        return {a : i.rendered for a, i in self.inst_kwargs.items()}

    def get_object(self):
        if self._object is None:
            kwargs = {a : v.get_object() for a, v in self.inst_kwargs.items()}
            self._object = Struct._create_object(self.type_name, **kwargs)
        return self._object

    def to_json(self):
        return {a : i.to_json() for a, i in self.inst_kwargs.items()}

    def __getitem__(self, attr_name):
        return self.inst_kwargs[attr_name]

    def __getattr__(self, attr_name):
        return self.inst_kwargs[attr_name]

    def __str__(self):
        return f'TycoInstance({self.type_name}, {self.inst_kwargs})'

    def __repr__(self):
        return self.__str__()

    def _error(self, message):
        fragment = self.fragment
        if fragment is None:
            for attr in self.inst_kwargs.values():
                attr_fragment = getattr(attr, 'fragment', None)
                if attr_fragment is not None:
                    fragment = attr_fragment
                    break
        source_lines = self.context._get_source_lines(getattr(fragment, 'source', None)) if fragment else None
        _raise_parse_error(message, fragment=fragment, source=getattr(fragment, 'source', None), source_lines=source_lines)


class TycoReference:                    # Lazy container class to refer to instances

    _unrendered = object()

    def __init__(self, context, inst_args, type_name):
        self.context = context
        self.inst_args = inst_args          # [TycoValue,...]
        self.type_name = type_name
        self.attr_name   = None           # set later
        self.is_nullable = None           # set later
        self.is_array    = None           # set later
        self.parent      = None           # set later
        self.rendered = self._unrendered
        self.fragment = None

    def make_copy(self):
        inst_args = [i.make_copy() for i in self.inst_args]
        ref = self.__class__(self.context, inst_args, self.type_name)
        ref.fragment = self.fragment
        return ref

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            if attr == 'type_name' and self.type_name != val:
                fragment = self.fragment
                _raise_parse_error(
                    f"Reference for '{self.attr_name}' expects type '{val}', but '{self.type_name}' was referenced",
                    fragment=fragment,
                    source=getattr(fragment, 'source', None),
                )
            setattr(self, attr, val)
        if self.is_array is True:
            fragment = self.fragment
            _raise_parse_error(
                f"Reference for '{self.attr_name}' is declared as a list, but a single reference was provided",
                fragment=fragment,
                source=getattr(fragment, 'source', None),
            )

    def set_parent(self, parent):           # not used for anything
        self.parent = parent

    def render_base_content(self):
        pass

    def render_references(self):
        if self.rendered is not self._unrendered:
            self._error('Reference was resolved more than once; this indicates a parser bug')
        if self.type_name not in self.context._structs:
            self._error(f"Unknown struct '{self.type_name}' referenced")
        struct = self.context._structs[self.type_name]
        self.rendered = struct.load_reference(self.inst_args)

    def render_templates(self):
        pass

    def _error(self, message):
        fragment = None
        for arg in self.inst_args:
            if getattr(arg, 'fragment', None):
                fragment = arg.fragment
                break
        fragment = fragment or self.fragment
        source_lines = self.context._get_source_lines(getattr(fragment, 'source', None)) if fragment else None
        _raise_parse_error(message, fragment=fragment, source=getattr(fragment, 'source', None), source_lines=source_lines)

    def __getitem__(self, attr_name):
        return self.rendered[attr_name]

    def __getattr__(self, attr_name):
        return self.rendered[attr_name]

    def get_object(self):
        return self.rendered.get_object()

    def to_json(self):
        return self.rendered.to_json()

    def __str__(self):
        return f'TycoReference({self.type_name}, {self.inst_args}, {self.rendered})'     # TODO make better

    def __repr__(self):
        return self.__str__()


class TycoArray:

    def __init__(self, context, content):
        self.context = context
        self.content = content            # [TycoInstance|TycoValue|TycoReference,...]
        self.type_name   = None           # set later
        self.attr_name   = None           # set later
        self.is_nullable = None           # set later
        self.is_array    = None           # set later
        self.parent      = None           # set later
        self._object = None
        self.fragment = None
        self.source = None

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            setattr(self, attr, val)
        for i in self.content:
            kwargs = {'is_nullable' : False, 'is_array' : False}
            if self.type_name is not None:
                kwargs['type_name'] = self.type_name
            if self.attr_name is not None:
                kwargs['attr_name'] = self.attr_name
            i.apply_schema_info(**kwargs)
        if self.is_array is False:
            self._error(
                f"Field '{self.attr_name}' is declared as a single value, but a list was provided. "
                f"Add [] to the schema definition if '{self.attr_name}' should accept multiple values."
            )

    def set_parent(self, parent):
        self.parent = parent
        for i in self.content:
            i.set_parent(parent)            # we ignore the TycoArray object itself for purposes of templating

    def render_base_content(self):
        for i in self.content:
            i.render_base_content()

    def render_references(self):
        for i in self.content:
            i.render_references()

    def render_templates(self):
        for i in self.content:
            i.render_templates()

    def make_copy(self):
        return self.__class__(self.context, [i.make_copy() for i in self.content])

    @property
    def rendered(self):
        return [i.rendered for i in self.content]

    def get_object(self):
        if self._object is None:
            self._object = [i.get_object() for i in self.content]
        return self._object

    def to_json(self):
        return [i.to_json() for i in self.content]

    def __str__(self):
        return f'TycoArray({self.type_name} {self.attr_name}: {self.content})'

    def __repr__(self):
        return self.__str__()

    def _error(self, message):
        fragment = self.fragment
        if fragment is None:
            for item in self.content:
                if getattr(item, 'fragment', None):
                    fragment = item.fragment
                    break
        source_lines = self.context._get_source_lines(getattr(fragment, 'source', None)) if fragment else None
        _raise_parse_error(message, fragment=fragment, source=getattr(fragment, 'source', None), source_lines=source_lines)


class TycoValue:

    TEMPLATE_REGEX = r'\{([\w\.]+)\}'
    base_types = {'str', 'int', 'bool', 'float', 'decimal', 'date', 'time', 'datetime'}
    _unrendered = object()

    def __init__(self, context, content):
        self.context = context
        self.content = content
        self.type_name   = None           # set later
        self.attr_name   = None           # set later
        self.is_nullable = None           # set later
        self.is_array    = None           # set later
        self.parent      = None           # set later
        self.is_literal_str = False
        self.rendered = self._unrendered
        self.fragment = content if isinstance(content, SourceString) else None
        self.source = getattr(content, 'source', None)

    def make_copy(self):
        attr = self.__class__(self.context, self.content)
        attr.type_name   = self.type_name
        attr.attr_name   = self.attr_name
        attr.is_nullable = self.is_nullable
        attr.is_array    = self.is_array
        attr.fragment = self.fragment
        attr.source = self.source
        return attr

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            setattr(self, attr, val)
        if self.is_array is True and not (self.is_nullable is True and self.content == 'null'):
            self._error(f"Expected a singular value for '{self.attr_name}', but found an array")
        if self.type_name is not None and self.type_name not in self.base_types:
            self._error(
                f"'{self.content}' must be referenced using {self.type_name}(...); implicit conversion isn't allowed"
            )

    def set_parent(self, parent):
        self.parent = parent

    def render_base_content(self):
        if None in (self.type_name, self.attr_name, self.is_nullable, self.is_array):
            self._error('Internal parser error: attribute metadata missing before rendering')
        content = self.content
        text = str(content)
        if self.is_nullable and text == 'null':
            rendered = None
        elif self.type_name == 'str':
            self.is_literal_str = text.startswith("'")
            if text[:3] in ("'''", '"""'):
                text = text[3:-3]
                if text.startswith(os.linesep):                 # strip single leading newline
                    text = text[len(os.linesep):]
            elif text[:1] in ("'", '"'):
                text = text[1:-1]
            rendered = text
        elif self.type_name == 'int':
            if text.startswith('0x'):
                base = 16
            elif text.startswith('0o'):
                base = 8
            elif text.startswith('0b'):
                base = 2
            else:
                base = 10
            try:
                rendered = int(text, base)
            except ValueError:
                self._error(f"'{text}' is not a valid integer literal")
        elif self.type_name == 'float':
            try:
                rendered = float(text)
            except ValueError:
                self._error(f"'{text}' is not a valid floating-point literal")
        elif self.type_name == 'decimal':
            try:
                rendered = decimal.Decimal(text)
            except decimal.InvalidOperation:
                self._error(f"'{text}' is not a valid decimal literal")
        elif self.type_name == 'bool':
            if text == 'true':
                rendered = True
            elif text == 'false':
                rendered = False
            else:
                self._error(
                    f"Boolean fields must be either 'true' or 'false', but '{text}' was provided"
                )
        elif self.type_name == 'date':
            try:
                rendered = datetime.date.fromisoformat(text)
            except ValueError:
                self._error(f"'{text}' is not a valid ISO-8601 date (YYYY-MM-DD)")
        elif self.type_name == 'time':
            try:
                rendered = datetime.time.fromisoformat(text)
            except ValueError:
                self._error(f"'{text}' is not a valid ISO-8601 time (HH:MM:SS)")
        elif self.type_name == 'datetime':
            try:
                rendered = datetime.datetime.fromisoformat(text)
            except ValueError:
                self._error(
                    f"'{text}' is not a valid ISO-8601 datetime (YYYY-MM-DD HH:MM:SS±TZ)"
                )
        else:
            self._error(f"Unsupported type '{self.type_name}'")
        self.rendered = rendered

    def render_references(self):
        pass

    def render_templates(self):
        if not self.type_name == 'str' or self.is_literal_str:
            return
        if self.is_nullable and self.rendered is None:
            return

        def template_render(match):
            obj = self.parent
            template_var = match.groups()[0]
            if template_var.startswith('..'):       # indicates parent
                template_var = template_var[1:]     # double for parent, triple for parent's parent etc
                while template_var.startswith('.'):
                    obj = obj.parent
                    if obj is None:
                        self._error(
                            f"Template '{match.group(0)}' references a parent that does not exist"
                        )
                    template_var = template_var[1:]     # strip off a leading .
            for i, attr in enumerate(template_var.split('.')):
                try:
                    obj = obj[attr]
                except KeyError:
                    if i == 0 and attr == 'global':
                        obj = self.context._globals
                    else:
                        self._error(
                            f"Template '{match.group(0)}' references unknown attribute '{attr}'"
                        )
            if obj.type_name not in ('str', 'int'):
                self._error(
                    f"Template '{match.group(0)}' can only insert strings or integers "
                    f"(got '{obj.type_name}')"
                )
            return str(obj.rendered)

        rendered = re.sub(self.TEMPLATE_REGEX, template_render, self.rendered)
        rendered = sub_escape_sequences(rendered)
        self.rendered = rendered

    def get_object(self):
        return self.rendered

    def to_json(self):
        if isinstance(self.rendered, (datetime.date, datetime.time, datetime.datetime)):
            return self.rendered.isoformat()
        elif isinstance(self.rendered, decimal.Decimal):
            return float(self.rendered)
        else:
            return self.rendered

    def __str__(self):
        text = f'TycoValue({self.type_name}, {self.content}'
        if self.rendered is not self._unrendered:
            text += f', {self.rendered}'
        text += ')'
        return text

    def __repr__(self):
        return self.__str__()

    def _error(self, message):
        fragment = self.fragment or self.content
        source_lines = self.context._get_source_lines(getattr(fragment, 'source', None) or self.source) if hasattr(self, 'context') and self.context else None
        _raise_parse_error(message, fragment=fragment, source=self.source, source_lines=source_lines)


class Struct(types.SimpleNamespace):

    registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(*kwargs)
        cls.registry[cls.__name__] = cls

    @classmethod
    def _create_object(cls, type_name, *args, **kwargs):
        if type_name not in cls.registry:
            cls.registry[type_name] = type(type_name, (cls,), {})
        obj = cls.registry[type_name](*args, **kwargs)
        obj.validate()
        return obj

    def __getitem__(self, key):
        return getattr(self, key)

    def validate(self):
        pass


def load(path):
    context = TycoContext()
    if os.path.isdir(path):
        dir_path = pathlib.Path(path)
        paths = [str(p) for p in dir_path.rglob('*.tyco')]
    else:
        paths = [str(path)]
    for path in paths:
        lexer = TycoLexer.from_path(context, path)
        lexer.process()
    context._render_content()
    return context


def loads(content):
    context = TycoContext()
    lines = _coerce_lines(content.splitlines(keepends=True), source='<string>')
    lexer = TycoLexer(context, lines)
    lexer.process()
    context._render_content()
    return context
