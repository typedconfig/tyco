#!/usr/bin/env python3

import os
import re
import sys
import enum
import types
import string
import decimal
import datetime
import itertools
import collections


__all__ = ['Struct', 'load']


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


def debug(*content):
    print(*content, file=sys.stderr)


def strip_comments(line):
    content, *comments = line.split('#', maxsplit=1)
    if comments and (invalid := set(comments[0].rstrip(os.linesep)) & ILLEGAL_STR_CHARS):
        raise Exception(f'Invalid characters in comments: {invalid}')
    return content.rstrip()


def is_whitespace(content):
    return re.match(r'\s*$', content)


def cached_property(func):
    @property
    def wrapper(self):
        cache_name = f'_{func.__name__}_cache'
        if not hasattr(self, cache_name):
            setattr(self, cache_name, func(self))
        return getattr(self, cache_name)
    return wrapper


class TycoLexer:

    ire = r'((?!\d)\w+)'            # regex to match identifiers
    GLOBAL_SCHEMA_REGEX = rf'([?])?{ire}(\[\])?\s+{ire}\s*:'
    STRUCT_BLOCK_REGEX  = rf'^{ire}:'
    STRUCT_SCHEMA_REGEX = rf'^\s+([*?])?{ire}(\[\])?\s+{ire}\s*:'
    STRUCT_DEFAULTS_REGEX = r'\s+{ire}\s*:'
    STRUCT_INSTANCE_REGEX = r'\s+-'

    @classmethod
    def from_path(cls, context, path):
        if path not in context._path_cache:
            with open(path) as f:
                lines = list(f.readlines())
            lexer = cls(context, lines)
            lexer.process()
            context._path_cache[path] = lexer
        return lexer

    def __init__(self, context, lines):
        self.context = context
        self.lines = collections.deque(lines)
        self.num_lines = len(lines)
        self.defaults = {}       # {type_name : {attr_name : TycoInstance|TycoValue|TycoArray|TycoReference}}

    def process(self):
        while self.lines:
            line = self.lines.popleft()
            if line.startswith('#include '):
                try:
                    path = line.split(maxsplit=1)[1].strip()
                    if not path:
                        raise Exception
                except Exception:
                    raise Exception(f'Invalid included path: {line}')
                lexer = self.__class__.from_path(self.context, path)
                lexer.process()
                for type_name, attr_defaults in lexer.defaults.items():
                    if type_name in self.defaults:
                        raise Exception(f'This should not happen: {struct.type_name} in {self.defaults}')
                    self.defaults[type_name] = attr_defaults.copy()
                continue
            if match := re.match(self.GLOBAL_SCHEMA_REGEX, line):
                self._load_global(line, match)
                continue
            elif match := re.match(self.STRUCT_BLOCK_REGEX, line):
                type_name = match.groups()[0]
                debug(f'Found match for {type_name}:')
                if type_name not in self.context._structs:
                    struct = self.context._add_struct(type_name)
                    self._load_schema(struct)
                struct = self.context._structs[type_name]
                self._load_local_defaults_and_instances(struct)
                continue
            elif not strip_comments(line):
                continue
            raise Exception(f'Malformatted config file: {line!r}')

    def _load_global(self, line, match):
        debug(f'Loading global: {line}')
        options, type_name, array_flag, attr_name = match.groups()
        is_array = array_flag == '[]'
        is_nullable = options == '?'
        default_text = line.split(':', maxsplit=1)[1].lstrip()
        if not default_text:
            raise Exception(f'Must provide a value when setting globals')
        self.lines.appendleft(default_text)
        attr, delim = self._load_tyco_attr2()
        attr.apply_schema_info(type_name=type_name, attr_name=attr_name, is_nullable=is_nullable, is_array=is_array)
        self.context._set_global_attr(attr_name, attr)

    def _load_schema(self, struct):
        debug(f'Loading schema for {struct}')
        if struct.type_name in self.defaults:
            raise Exception(f'This should not happen: {struct.type_name} in {self.defaults}')
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
                    raise Exception(f'Schema attribute missing trailing colon: {content!r}')
                break
            line = self.lines.popleft()
            options, type_name, array_flag, attr_name = match.groups()
            if attr_name in struct.attr_types:
                raise Exception(f'Duplicate attribute found for {attr_name} in {struct.type_name}: {line}')
            struct.attr_types[attr_name] = type_name
            if (is_array := array_flag == '[]'):
                struct.array_keys.add(attr_name)
            if options == '*':
                if is_array:
                    raise Exception(f'Can not set a primary key on an array')
                struct.primary_keys.append(attr_name)
            elif options == '?':
                struct.nullable_keys.add(attr_name)
            default_text = line.split(':', maxsplit=1)[1].lstrip()
            default_content = strip_comments(default_text)
            if default_content:
                self.lines.appendleft(default_text)
                attr, delim = self._load_tyco_attr2()
                self.defaults[struct.type_name][attr_name] = attr

    def _load_local_defaults_and_instances(self, struct):
        debug(f'Loading defaults and instances for {struct}')
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
                raise Exception(f'Can not add schema attributes after initial construction')
            line = self.lines.popleft()
            if match := re.match(self.STRUCT_DEFAULTS_REGEX, line):
                attr_name = match.groups()
                debug(f'New default for {struct}: {attr_name}')
                if attr_name not in struct.attr_types:
                    raise Exception(f'Setting invalid default of {attr_name} for {struct}')
                default_text = line.split(':', maxsplit=1)[1].lstrip()
                if strip_comments(default_text):
                    self.lines.appendleft(default_text)
                    attr, delim = self._load_tyco_attr2()
                    self.defaults[struct.type_name][attr_name] = attr
                else:
                    self.defaults[struct.type_name].pop(attr_name, None)          # if empty remove previous defaults
            elif match := re.match(self.STRUCT_INSTANCE_REGEX, line):
                debug(f'Parsing new instance for {struct}')
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
                    attr, delim = self._load_tyco_attr2(good_delim=(',', os.linesep), pop_empty_lines=False)
                    inst_args.append(attr)
                struct.create_instance(inst_args, self.defaults[struct.type_name])

    def _load_tyco_attr2(self, good_delim=(os.linesep,), bad_delim='', pop_empty_lines=True):
        bad_delim = set(bad_delim) | set('()[],') - set(good_delim)
        if not self.lines:
            raise Exception(f'Syntax error: no content found')
        if match := re.match(rf'{self.ire}\s*:\s*', self.lines[0]):     # need to exclude times w/ colons
            attr_name = match.groups()[0]
            self.lines[0] = self.lines[0][match.span()[1]:]
        else:
            attr_name = None
        ch = self.lines[0][:1]
        if ch == '[':                                               # inline array
            self.lines[0] = self.lines[0][1:]
            content = self._load_array(']')
            attr = TycoArray(self.context, content)
            delim = self._strip_next_delim(good_delim)
        elif match := re.match(r'(\w+)\(', self.lines[0]):           # inline instance/reference
            type_name = match.groups()[0]
            self.lines[0] = self.lines[0][match.span()[1]:]
            inst_args = self._load_array(')')
            if type_name not in self.context._structs or self.context._structs[type_name].primary_keys:
                attr = TycoReference(self.context, inst_args, type_name)
            else:
                default_kwargs = self.defaults[type_name]
                attr = self.context._structs[type_name].create_inline_instance(inst_args, default_kwargs)
            delim = self._strip_next_delim(good_delim)
        elif ch in ('"', "'"):                                      # quoted string
            if (triple := ch*3) == self.lines[0][:3]:
                quoted_string = self._load_triple_string(triple)
            else:
                quoted_string = self._load_single_string(ch)
            attr = TycoValue(self.context, quoted_string)
            delim = self._strip_next_delim(good_delim)
        else:
            attr, delim = self._strip_next_attr_and_delim(good_delim, bad_delim)
        self.lines[0] = self.lines[0].lstrip(' \t')                 # do not strip off newlines
        if pop_empty_lines and not self.lines[0]:
            self.lines.popleft()
        if attr_name is not None:
            attr.apply_schema_info(attr_name=attr_name)
        return attr, delim

    def _strip_next_delim(self, good_delim):
        delim_regex = '^' + '|'.join(re.escape(d) for d in good_delim)
        if not (match := re.match(delim_regex, self.lines[0])):
            if os.linesep in good_delim and not (content := strip_comments(self.lines[0])):
                delim = os.linesep                      # handles the case where we only have trailing comments
                self.lines[0] = ''
                return delim
            raise Exception(f'Should have found next delimiter {good_delim}: {self.lines[0]!r}')
        delim = match.group()
        start, end = match.span()
        self.lines[0] = self.lines[0][end:]
        return delim

    def _strip_next_attr_and_delim(self, good_delim, bad_delim):
        all_content = strip_comments(self.lines[0]) + os.linesep
        all_delim = list(good_delim) + list(bad_delim)
        delim_regex = '|'.join(re.escape(d) for d in all_delim)
        if not (match := re.search(delim_regex, all_content)):
            raise Exception(f'Should have found some delimiter {all_delim}: {self.lines[0]!r}')
        delim = match.group()
        if delim in bad_delim:
            raise Exception(f'Bad delim: {delim}')
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
                raise Exception(f'Could not find {closing_char}')
            if not strip_comments(self.lines[0]):                       # can have newlines within the array
                self.lines.popleft()
                continue
            if self.lines[0].startswith(closing_char):                  # can happen with a trailing comma
                self.lines[0] = self.lines[0][1:]
                break
            attr, delim = self._load_tyco_attr2(good_delims, bad_delims)
            array.append(attr)
            if delim == closing_char:
                break
        return array

    def _load_triple_string(self, triple):
        is_literal = triple == "'''"
        start = 3
        all_contents = []
        while True:
            if not self.lines:
                raise Exception('Unclosed triple quote')
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
            raise Exception(f'Invalid characters found in literal multiline string: {invalid}')
        self.lines.appendleft(remainder)
        return final_content

    def _load_single_string(self, ch):
        is_literal = ch == "'"
        start = 1
        line = self.lines.popleft()
        while True:
            end = line.find(ch, start)
            if end == -1:
                raise Exception(f'Unclosed single-line string for {ch!r}: {line!r}')
            if is_literal or line[end-1] != '\\':       # this is an escaped quote
                break
            start = end + 1
        end += 1                            # include quote at the end
        final_content = line[:end]
        remainder = line[end:]
        if invalid := set(final_content) & ILLEGAL_STR_CHARS:
            raise Exception(f'Invalid characters found in literal string: {invalid}')
        self.lines.appendleft(remainder)
        return final_content


class TycoContext:

    def __init__(self):
        self._path_cache = {}       # {path : TycoPath()}
        self._structs    = {}       # {type_name : TycoStruct()}
        self._globals    = {}       # {attr_name : TycoValue|TycoInstance|TycoArray|TycoReference}

    def _set_global_attr(self, attr_name, attr):
        if attr_name in self._globals:
            raise Exception(f'Duplicate global attribute: {attr_name}')
        self._globals[attr_name] = attr

    def _add_struct(self, type_name):
        self._structs[type_name] = struct = TycoStruct(self, type_name)
        debug(f'Adding new struct {struct}')
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

    def get_global_objects(self):
        return {a : i.get_object() for a, i in self._globals.items()}

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
                    raise Exception(f'Can not use positional values after keyed values: {inst_args}')
                attr.attr_name = self.attr_names[i]
            else:
                kwargs_only = True
            inst_kwargs[attr.attr_name] = attr
        complete_kwargs = self._resolve_complete_kwargs(inst_kwargs, default_kwargs)
        return TycoInstance(self.context, self.type_name, complete_kwargs)

    def load_primary_keys(self):
        if not self.primary_keys:
            return
        for inst in self.instances:
            key = tuple(getattr(inst, k).rendered for k in self.primary_keys)
            if key in self.mapped_instances:
                raise Exception(f'{key} already found for {self.type_name}: {self.mapped_instances[key]}')
            self.mapped_instances[key] = inst

    def load_reference(self, inst_args):
        inst_kwargs = {}
        kwargs_only = False
        for i, attr in enumerate(inst_args):
            if not attr.attr_name:
                if kwargs_only:
                    raise Exception(f'Can not use positional values after keyed values: {inst_args}')
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
            raise Exception(f'Unable to find reference of {self.type_name}({key})')
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
                raise Exception(f'Invalid attribute {attr_name} for {self}')
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

    def make_copy(self):
        inst_kwargs = {a : i.make_copy() for a, i in self.inst_kwargs.items()}
        return self.__class__(self.context, self.type_name, inst_kwargs)

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            if attr == 'type_name' and self.type_name != val:
                raise Exception(f'Expected {self.type_name} for {self.parent}.{self.attr_name} and instead have {self}')
            setattr(self, attr, val)
        if self.is_array is True:
            raise Exception(f'Expected array for {self.parent}.{self.attr_name}, instead have {self}')

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

    def make_copy(self):
        inst_args = [i.make_copy() for i in self.inst_args]
        return self.__class__(self.context, inst_args, self.type_name)

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            if attr == 'type_name' and self.type_name != val:
                raise Exception(f'Expected {self.type_name} for {self.parent}.{self.attr_name} and instead have {self}')
            setattr(self, attr, val)
        if self.is_array is True:
            raise Exception(f'Expected array for {self.parent}.{self.attr_name}, instead have {self}')

    def set_parent(self, parent):           # not used for anything
        self.parent = parent

    def render_base_content(self):
        pass

    def render_references(self):
        if self.rendered is not self._unrendered:
            raise Exception(f'Rendered multiple times {self}')
        if self.type_name not in self.context._structs:
            raise Exception(f'Bad type name for reference: {self.type_name} {self.inst_args}')
        struct = self.context._structs[self.type_name]
        self.rendered = struct.load_reference(self.inst_args)

    def render_templates(self):
        pass

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

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            setattr(self, attr, val)
        for i in self.content:
            i.apply_schema_info(type_name=self.type_name, attr_name=self.attr_name, is_nullable=False, is_array=False)
        if self.is_array is False:
            raise Exception(f'Schema for {self.parent}.{self.attr_name} needs to indicate array with []')

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

    def make_copy(self):
        attr = self.__class__(self.context, self.content)
        attr.type_name   = self.type_name
        attr.attr_name   = self.attr_name
        attr.is_nullable = self.is_nullable
        attr.is_array    = self.is_array
        return attr

    def apply_schema_info(self, **kwargs):
        for attr, val in kwargs.items():
            setattr(self, attr, val)
        if self.is_array is True and not (self.is_nullable is True and self.content == 'null'):
            raise Exception(f'Array expected for {self.parent}.{self.attr_name}: {self}')
        if self.type_name is not None and self.type_name not in self.base_types:
            raise Exception(f'{self.type_name} expected for {self.content}, likely needs {self.type_name}({self.content})')

    def set_parent(self, parent):
        self.parent = parent

    def render_base_content(self):
        if None in (self.type_name, self.attr_name, self.is_nullable, self.is_array):
            raise Exception(f'Attributes not set {self.attr_name}: {self}')           # TODO remove when mature
        content = self.content
        if self.is_nullable and content == 'null':
            rendered = None
        elif self.type_name == 'str':
            self.is_literal_str = content.startswith("'")
            if content[:3] in ("'''", '"""'):
                content = content[3:-3]
                if content.startswith(os.linesep):                 # strip single leading newline
                    content = content[len(os.linesep):]
            elif content[:1] in ("'", '"'):
                content = content[1:-1]
            rendered = content
        elif self.type_name == 'int':
            if content.startswith('0x'):
                base = 16
            elif content.startswith('0o'):
                base = 8
            elif content.startswith('0b'):
                base = 2
            else:
                base = 10
            rendered = int(content, base)
        elif self.type_name == 'float':
            rendered = float(content)
        elif self.type_name == 'decimal':
            rendered = decimal.Decimal(content)
        elif self.type_name == 'bool':
            if content == 'true':
                rendered = True
            elif content == 'false':
                rendered = False
            else:
                raise Exception(f'Boolean {self.attr_name} for {self.parent} not in (true, false): {content}')
        elif self.type_name == 'date':
            rendered = datetime.date.fromisoformat(content)
        elif self.type_name == 'time':
            rendered = datetime.time.fromisoformat(content)
        elif self.type_name == 'datetime':
            rendered = datetime.datetime.fromisoformat(content)
        else:
            raise Exception(f'Unknown type of {self.type_name}')
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
                        raise Exception(f'Traversing parents hit base instance')
                    template_var = template_var[1:]     # strip off a leading .
            for attr in template_var.split('.'):
                obj = obj[attr]
            if obj.type_name not in ('str', 'int'):
                raise Exception(f'Can not templatize objects other than strings or ints: {obj} ({self})')
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
    tyco_lexer = TycoLexer.from_path(context, path)
    tyco_lexer.process()
    context._render_content()
    return context
