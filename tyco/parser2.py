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

GLOBAL_SCHEMA_REGEX = r'([?])?(\w+)(\[\])?\s+(\w+)\s*:'
STRUCT_BLOCK_REGEX  = r'^([a-zA-Z_][a-zA-Z0-9_]*):'
STRUCT_SCHEMA_REGEX = r'^\s+([*?])?(\w+)(\[\])?\s+(\w+)\s*:'


class TycoContext:

    base_types = {'str', 'int', 'bool', 'float', 'decimal', 'date', 'time', 'datetime'}

    def __init__(self):
        self.path_cache = {}       # {path : TycoLexer()}
        self.globals    = {}       # {attr_name : TycoInstance|TycoValue}
        self.structs    = {}       # {type_name : TycoStruct()}

    def render_content(self):
        ...


class TycoLexer:

    @classmethod
    def from_path(cls, context, path):
        if path not in context.path_cache:
            with open(path) as f:
                lines = list(f.readlines())
            lexer = cls(context, lines)
            lexer.process()
            context.path_cache[path] = lexer
        return lexer

    def __init__(self, context, lines):
        self.context = context
        self.lines = collections.deque(lines)
        self.defaults = {}       # {type_name : {attr_name : TycoInstance|TycoValue}}

    def process(self):
        while self.lines:
            line = self.lines.popleft()
            if match := re.match(GLOBAL_SCHEMA_REGEX, line):
                self._load_global(line, match)
            elif match := re.match(STRUCT_BLOCK_REGEX, line):
                type_name = match.groups()[0]
                debug(f'Found match for {type_name}:')
                if type_name not in self.context.structs:
                    struct = self.context.add_struct(type_name)
                    self._load_schema(struct)
                struct = self.context.structs[type_name]
                self._load_local_defaults_and_instances(struct)
            elif match := re.match(rf'^#include\s+(\w+)', line):
                path = match.groups()[0]
                lexer = self.__class__.from_path(self.context, path)
                lexer.process()
            elif not strip_comments(line):                # blank or comments
                pass
            else:
                raise Exception(f'Malformatted config file: {line}')



"""
class TycoStr(str):

    def __new__(cls, text, line=0, col=0):
        obj = str.__new__(cls, text)
        obj.line = line
        obj.col = col
        return obj

    def __getitem__(self, key):
        if isinstance(key, slice):
            start = key.start
            if start is None:
                start = 0
            elif start < 0:
                start = len(self) + start
            start = max(0, start)
            sub = super().__getitem__(key)
            return type(self)(sub, line=self.line, col=self.col + start)
        else:
            pos = key
            if pos < 0:
                pos = len(self) + pos
            pos = max(0, pos)
            sub = super().__getitem__(key)
            return type(self)(sub, line=self.line, col=self.col+pos)

    def __add__(self, other):
        result = super().__add__(str(other))
        return type(self)(result, line=self.line, col=self.col)

    def __radd__(self, other):
        result = str(other) + self
        if isinstance(other, type(self)):
            return type(self)(result, line=other.line, col=other.col)
        else:
            return type(self)(result, line=self.line, col=self.col)

    @classmethod
    def join(cls, iterable, sep=''):
        strs = (str(x) for x in iterable)
        result = sep.join(strs)
        for item in iterable:
            if isinstance(item, cls):
                return cls(result, line=item.line, col=item.col)
        return result


class TycoBlock:

    class BlockType(enum.Enum):
        GLOBAL_ATTR  = enum.auto()
        STRUCT_DEF   = enum.auto()
        INCLUDE_FILE = enum.auto()
        WHITESPACE   = enum.auto()

    @classmethod
    def from_path(cls, context, path):
        if path not in context.path_cache:
            with open(path) as f:
                lines = list(f.readlines())
            lexer = cls(context, lines)
            lexer.process()
            context.path_cache[path] = lexer
        return lexer

    def __init__(self, block_type):
        self.block_type = block_type
        self.contents = []



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


def debug(content):
    print(content, file=sys.stderr)


def strip_comments(line):
    content, *comments = line.rstrip('\r\n').split('#', maxsplit=1)
    if comments and (invalid := set(comments[0]) & ILLEGAL_STR_CHARS):
        raise Exception(f'Invalid characters in comments: {invalid}')
    return content.strip()


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


class TycoContext:

    base_types = {'str', 'int', 'bool', 'float', 'decimal', 'date', 'time', 'datetime'}

    def __init__(self):
        self.path_cache = {}       # {path : TycoPath()}
        self.structs    = {}       # {type_name : TycoStruct()}
        self.globals    = {}       # {attr_name : TycoInstance|TycoValue}
        self._update_type_info()

    def _update_type_info(self):
        valid_types = '|'.join(self.base_types | self.structs.keys())        # TODO test old python
        self.schema_regex = rf'^\s+([*?])?({valid_types})(\[\])?\s+(\w+)\s*:'
        self.global_regex = rf'([?])?({valid_types})(\[\])?\s+(\w+)\s*:'

    def add_struct(self, type_name):
        self.structs[type_name] = struct = TycoStruct(self, type_name)
        debug(f'Adding new struct {struct}')
        self._update_type_info()
        return struct

    def render_content(self):
        for val in self.globals.values():
            val.render_content()
        for struct in self.structs.values():
            for inst in struct.instances:
                inst.render_content()

    def to_json(self):
        json_content = {}
        for attr_name, val in self.globals.items():
            json_content[attr_name] = val.to_json()
        for type_name, struct in self.structs.items():
            json_content[type_name] = struct_content = []
            for instance in struct.instances:
                struct_content.append(instance.to_json())
        return json_content


class TycoLexer:

    @classmethod
    def from_path(cls, context, path):
        if path not in context.path_cache:
            with open(path) as f:
                lines = list(f.readlines())
            lexer = cls(context, lines)
            lexer.process()
            context.path_cache[path] = lexer
        return lexer

    def __init__(self, context, lines):
        self.context = context
        self.lines = collections.deque(lines)
        self.num_lines = len(lines)
        self.defaults = {}       # {type_name : {attr_name : TycoInstance|TycoValue}}

    def process(self):
        while self.lines:
            line = self.lines.popleft()
            if match := re.match(self.context.global_regex, line):
                self._load_global(line, match)
            elif match := re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):', line):
                type_name = match.groups()[0]
                debug(f'Found match for {type_name}:')
                if type_name not in self.context.structs:
                    struct = self.context.add_struct(type_name)
                    self._load_schema(struct)
                struct = self.context.structs[type_name]
                self._load_local_defaults_and_instances(struct)
            elif match := re.match(rf'^#include\s+(\w+)', line):
                path = match.groups()[0]
                lexer = self.__class__.from_path(self.context, path)
                lexer.process()
            elif not strip_comments(line):                # blank or comments
                pass
            else:
                raise Exception(f'Malformatted config file: {line}')

    def _load_global(self, line, match):                                #TODO check hasn't already been declared
        debug(f'Loading global: {line}')
        options, type_name, array_flag, attr_name = match.groups()
        is_array = array_flag == '[]'
        if (is_nullable := options == '?'):
            if is_array:
                raise Exception(f'Can not set an array to be nullable')
        default_text = line.split(':', maxsplit=1)[1].lstrip()
        if not default_text:
            raise Exception(f'Must provide a value when setting globals')
        self.lines.appendleft(default_text)
        self.context.globals[attr_name] = self._load_tyco_attr(type_name, is_array, is_nullable, attr_name, parent=None)

    def _load_schema(self, struct):
        debug(f'Loading schema for {struct}')
        self.defaults[struct.type_name] = {}
        while True:
            if not self.lines:
                break
            content = strip_comments(self.lines[0])
            if not content:                 # blank lines or comments
                self.lines.popleft()
                continue
            if not (match := re.match(self.context.schema_regex, self.lines[0])):       #TODO fix when trailing comma left out in schema
                break
            line = self.lines.popleft()
            options, type_name, array_flag, attr_name = match.groups()
            struct.attr_types[attr_name] = type_name
            if (is_array := array_flag == '[]'):
                struct.array_keys.add(attr_name)
            if options == '*':
                if is_array:
                    raise Exception(f'Can not set a primary key on an array')
                struct.primary_keys.append(attr_name)
            elif (is_nullable := options == '?'):
                if is_array:
                    raise Exception(f'Can not set an array to be nullable')
                struct.nullable_keys.add(attr_name)
            default_text = line.split(':', maxsplit=1)[1].lstrip()
            if default_text:
                self.lines.appendleft(default_text)
                self.defaults[struct.type_name][attr_name] = self._load_tyco_attr(type_name, is_array, is_nullable, attr_name, parent=None)
                if not self.lines[0] == os.linesep:
                    raise Exception(f'Error in parser - should leave empty newline after attr processing')
                self.lines.popleft()

    def _load_tyco_attr(self, type_name, is_array, is_nullable, attr_name, parent=None, braces_stack=()):
        if not braces_stack:
            braces_stack = []
        if is_array:
            if not self.lines or not self.lines[0].startswith('['):
                raise Exception(f'Must use [] brackets to create array')
            braces_stack.append(self.lines[0][:1])
            self.lines[0] = self.lines[0][1:]
            array = []
            while True:
                if not self.lines:
                    raise Exception(f'Reached end of file while processing object')
                if is_whitespace(self.lines[0]):
                    self.lines.popleft()
                    continue
                elif self.lines[0].lstrip().startswith(']'):
                    self.lines[0] = self.lines[0].split(']', maxsplit=1)[1]
                    braces_stack.pop()               # pops off the [ character
                    break
                array.append(self._load_tyco_object(type_name, is_nullable, attr_name, parent, braces_stack))
            return array
        else:
            return self._load_tyco_object(type_name, is_nullable, attr_name, parent, braces_stack)

    def _load_tyco_object(self, type_name, is_nullable, attr_name, parent, braces_stack):
        if type_name in self.context.structs:
            struct = self.context.structs[type_name]
            return self._create_inline_instance(struct, type_name, is_nullable, attr_name, parent, braces_stack)
        else:
            return self._create_tyco_value(type_name, is_nullable, attr_name, parent, braces_stack)

    def _create_inline_instance(self, struct, type_name, is_nullable, attr_name, parent, braces_stack):
        if not self.lines:
            raise Exception(f'No content found for {struct}')
        if is_nullable:
            content, *remainder = self.lines[0].split(maxsplit=1)
            if content == 'null':
                remainder = '' if not remainder else remainder[0]
                trailing_comma_regex = r'[ \t]*,[ \t]*'                         #TODO abstract this to a function
                if re.match(trailing_comma_regex, remainder):
                    remainder = re.sub(trailing_comma_regex, '', remainder, count=1)
                elif not strip_comments(remainder):                         # empty line
                    remainder = '\n'
                self.lines[0] = remainder
                return TycoValue(self.context, type_name, is_nullable, attr_name, content)
        if not self.lines[0].lstrip().startswith(f'{struct.type_name}('):
            error = 'Must be a {struct} object'
            if is_nullable:
                error += ' or null'
            raise Exception(error)
        inst_kwargs = {}
        require_kwargs = False
        braces_stack.append('(')
        self.lines[0] = self.lines[0].split('(', maxsplit=1)[1].lstrip()
        while True:
            if not self.lines:
                raise Exception(f'Reached end of file while processing object')
            if is_whitespace(self.lines[0]):
                self.lines.popleft()
                continue
            elif self.lines[0].lstrip().startswith(')'):
                braces_stack.pop()
                remainder = self.lines[0].split(')', maxsplit=1)[1]
                trailing_comma_regex = r'[ \t]*,[ \t]*'
                if re.match(trailing_comma_regex, remainder):
                    remainder = re.sub(trailing_comma_regex, '', remainder, count=1)
                elif not strip_comments(remainder):                         # empty line
                    remainder = '\n'
                else:
                    raise Exception('Can not have additional content following )')
                self.lines[0] = remainder
                break
            if match := re.match(r'(\w+)\s*:', self.lines[0]):
                require_kwargs = True
                attr_name = match.groups()[0]
                if attr_name not in struct.attr_types:
                    raise Exception(f'Could not find attribute {attr_name} for {struct}')
                self.lines[0] = self.lines[0].split(':', maxsplit=1)[1].lstrip()
            else:
                if require_kwargs:
                    raise Exception(f'Can not use positional arguments after kwargs: {attr_name}')
                attr_name = struct.attr_position[len(inst_kwargs)]
            type_name = struct.attr_types[attr_name]
            is_array = attr_name in struct.array_keys
            # we set the parent to None here and then stitch it together from the get_inline_instance call
            inst_kwargs[attr_name] = self._load_tyco_attr(type_name, is_array, is_nullable, attr_name, parent=None, braces_stack=braces_stack)
        return struct.get_inline_instance(inst_kwargs, self.defaults[struct.type_name], attr_name, parent)

    def _create_tyco_value(self, type_name, is_nullable, attr_name, parent, braces_stack):
        if not self.lines:
            raise Exception('Unable to create value')
        line = self.lines.popleft()
        if not line:
            raise Exception('Unable to create value')
        if (ch := line[0]) in ('"', "'"):
            if type_name != 'str':
                raise Exception('Invalid use of quotes with {type_name}')
            if (triple := ch*3) == line[:3]:          # triple-quoted multi-line string
                start = 3
                all_contents = []
                while True:
                    end = line.find(triple, start)
                    if end != -1:
                        end += 3                      # include the triple quote at end
                        content = line[:end]
                        remainder = line[end:]
                        all_contents.append(content)
                        break
                    all_contents.append(line)
                    if not self.lines:
                        raise Exception('Unclosed triple quote')
                    line = self.lines.popleft()
                    start = 0
                for i in range(2):                  # edge case: there can be a max of 2 additional quotes
                    if remainder.startswith(ch):
                        all_contents[-1] += ch
                        remainder = remainder[1:]
                    else:
                        break
                print('HERE', all_contents, file=sys.stderr)
                final_content = ''.join(all_contents)
                if invalid := set(final_content) & ILLEGAL_STR_CHARS_MULTILINE:
                    raise Exception(f'Invalid characters found in literal multiline string: {invalid}')
            else:
                is_literal = ch == "'"
                start = 1
                while True:
                    end = line.find(ch, start)
                    if end == -1:
                        raise Exception(f'Unclosed single-line string: {ch}')
                    if is_literal or line[end-1] != '\\':
                        break
                    start = end + 1
                end += 1                            # include quote at the end
                final_content = line[:end]
                remainder = line[end:]
                if invalid := set(final_content) & ILLEGAL_STR_CHARS:
                    raise Exception(f'Invalid characters found in literal string: {invalid}')
            trailing_comma_regex = r'[ \t]*,[ \t]*'
            if re.match(trailing_comma_regex, remainder):
                remainder = re.sub(trailing_comma_regex, '', remainder, count=1)
            elif not strip_comments(remainder):                         # empty line
                remainder = '\n'
            else:
                raise Exception('Can not have additional content following quote')
            self.lines.appendleft(remainder)
        else:
            inf = float('inf')
            if (first_comma := line.find(',')) == -1: first_comma = inf             # using inf instead of -1 because it
            if (first_paren := line.find(')')) == -1: first_paren = inf             # makes comparison and if/else cleaner
            if (first_brack := line.find(']')) == -1: first_brack = inf

            looking_for_paren = braces_stack and braces_stack[-1] == '('
            looking_for_brack = braces_stack and braces_stack[-1] == '['

            if looking_for_paren:
                if first_brack < first_comma or first_brack < first_paren:
                    raise Exception('Malformed: closing ] found when looking for closing )')
                if first_comma < first_paren:                                               # we find the comma first
                    final_content = line[:first_comma]
                    self.lines.appendleft(line[first_comma+1:].lstrip())                    # strip the comma
                    if not self.lines[0]:
                        self.lines[0] = os.linesep
                elif first_paren < first_comma:                                             # we find the paren first
                    final_content = line[:first_paren]
                    self.lines.appendleft(line[first_paren:].lstrip())                      # don't strip the paren
                else:                                                                       # we haven't found either
                    final_content = strip_comments(line)
                    self.lines.appendleft(os.linesep)                                       # to indicate that we've hit EOL
            elif looking_for_brack:
                if first_paren < first_comma or first_paren < first_brack:
                    raise Exception('Malformed: closing ) found when looking for closing ]')
                if first_comma < first_brack:                                               # we find the comma first
                    final_content = line[:first_comma]
                    self.lines.appendleft(line[first_comma+1:].lstrip())                    # strip the comma
                    if not self.lines[0]:
                        self.lines[0] = os.linesep
                elif first_brack < first_comma:                                             # we find the brack first
                    final_content = line[:first_brack]
                    self.lines.appendleft(line[first_brack:].lstrip())                      # don't strip the brack
                else:                                                                       # we haven't found either
                    final_content = strip_comments(line)
                    self.lines.appendleft(os.linesep)                                       # to indicate that we've hit EOL
            else:
                if first_paren < first_comma:
                    raise Exception('Malformed: closing ) found when looking comma or EOL')
                if first_brack < first_comma:
                    raise Exception('Malformed: closing ] found when looking comma or EOL')
                if first_comma != inf:                                                      # we always allow trailing commas
                    final_content = line[:first_comma]
                    self.lines.appendleft(line[first_comma+1:].lstrip())                    # strip the comma
                else:
                    final_content = strip_comments(line)
                    self.lines.appendleft(os.linesep)                                       # to indicate that we've hit EOL
        val = TycoValue(self.context, type_name, is_nullable, attr_name, final_content)
        val.parent = parent
        return val

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
            if not self.lines[0].startswith(' '):  # start of a new struct
                break
            if match := re.match(self.context.schema_regex, self.lines[0]):
                raise Exception(f'Can not add schema attributes after initial construction')
            line = self.lines.popleft()
            if match := re.match(r'  (\w+)\s*:', line):         # DEFAULTS
                attr_name = match.groups()
                debug(f'New default for {struct}: {attr_name}')
                if attr_name not in struct.attr_types:
                    raise Exception('Setting invalid default of {attr_name} for {struct}')
                default_text = line.split(':', maxsplit=1)[1].lstrip()
                if default_text:
                    self.lines.appendleft(default_text)
                    if attr_name not in struct.attr_types:
                        raise Exception(f'Invalid default {attr_name} set for {struct}')
                    type_name = struct.attr_types[attr_name]
                    is_array = attr_name in struct.array_keys
                    is_nullable = attr_name in struct.nullable_keys
                    self.defaults[struct.type_name][attr_name] = self._load_tyco_attr(type_name, is_array, is_nullable, attr_name)
                    if not self.lines[0] == os.linesep:
                        raise Exception(f'Error in parser - should leave empty newline after attr processing')
                    self.lines.popleft()
                else:
                    if attr_name not in struct.attr_types:
                        raise Exception(f'Invalid default {attr_name} set for {struct}')
                    self.defaults[struct.type_name].pop(attr_name, None)          # if empty remove previous defaults
            elif line.startswith('  -'):                        # INSTANCES
                debug(f'Parsing new instance for {struct}')
                inst_kwargs = {}
                require_kwargs = False
                self.lines.appendleft(line[3:].lstrip())
                while True:
                    if not self.lines:
                        raise Exception(f'Ran out of content processing instance')
                    if match := re.match(r'\s*(\w+)\s*:', self.lines[0]):
                        require_kwargs = True
                        attr_name = match.groups()[0]
                        if attr_name not in struct.attr_types:
                            raise Exception(f'Could not find attribute {attr_name} for {struct}')
                        self.lines[0] = self.lines[0].split(':', maxsplit=1)[1].lstrip()
                    else:
                        if require_kwargs:
                            raise Exception(f'Can not use positional arguments after kwargs: {attr_name}')
                        attr_name = struct.attr_position[len(inst_kwargs)]
                    type_name = struct.attr_types[attr_name]
                    is_array = attr_name in struct.array_keys
                    is_nullable = attr_name in struct.nullable_keys
                    inst_kwargs[attr_name] = self._load_tyco_attr(type_name, is_array, is_nullable, attr_name)
                    remaining_content = strip_comments(self.lines[0])
                    if not remaining_content:
                        self.lines[0] = os.linesep
                    if self.lines[0] == os.linesep:                                     # we're done with the line
                        self.lines.popleft()
                        while self.lines:
                            next_content = strip_comments(self.lines[0])
                            if not next_content:
                                self.lines.popleft()
                            else:
                                break
                        if not self.lines or not self.lines[0].startswith('   '):       # spaces indicates more attrs
                            break
                struct.create_base_instance(inst_kwargs, self.defaults[struct.type_name])


class TycoStruct:

    def __init__(self, context, type_name):
        self.context = context
        self.type_name = type_name
        self.attr_types = collections.OrderedDict()     # {attr_name : type_name}
        self.primary_keys = []                          # [attr_name,...]               #TODO consolidate all of these to object
        self.nullable_keys = set()                      # {attr_name,...}               #TODO support this
        self.array_keys = set()                         # {attr_name,...}
        self.instances = []                             # [TycoInstance(),...]
        self.mapped_instances = {}                      # {primary_keys : TycoInstance}     #TODO check primary keys for valid/invalid characters
        self.schema_locked = False                                                          #TODO check duplicate primary key instances

    @cached_property
    def attr_position(self):
        return dict(enumerate(self.attr_types))

    @cached_property
    def primary_position(self):
        return dict(enumerate(self.primary_keys))

    def create_base_instance(self, inst_kwargs, default_kwargs):           # TODO what happens when someone uses references/templates here
        attr_name = None
        complete_kwargs = self._resolve_complete_kwargs(inst_kwargs, default_kwargs)
        inst = TycoInstance(self.context, self, attr_name, complete_kwargs)
        self.instances.append(inst)
        if self.primary_keys:
            key = tuple(getattr(inst, k).content for k in self.primary_keys)
            self.mapped_instances[key] = inst
        debug(f'Created new instance for {self}: {inst}')

    def get_inline_instance(self, inst_kwargs, default_kwargs, attr_name, parent):
        if self.primary_keys:                               # can only be a reference
            key = tuple(inst_kwargs[attr_name].content for attr_name in self.primary_keys)
            return self.mapped_instances[key]
        else:
            complete_kwargs = self._resolve_complete_kwargs(inst_kwargs, default_kwargs)
            inst = TycoInstance(self.context, self, attr_name, complete_kwargs)
            inst.parent = parent
            return inst

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
        return complete_kwargs

    def __str__(self):
        return f'TycoStruct({self.type_name})'

    def __repr__(self):
        return self.__str__()


class TycoInstance:

    def __init__(self, context, struct, attr_name, inst_kwargs):
        self.context = context
        self.struct = struct
        self.attr_name = attr_name          # attr_name of the parent TycoInstance, can be None
        self.inst_kwargs = inst_kwargs      # {attr_name : TycoInstance|TycoValue}
        self.parent = None
        self._apply_parent()

    def _apply_parent(self):
        for val in self.inst_kwargs.values():
            if not isinstance(val, list):
                val = [val]
            for v in val:
                v.parent = self

    def make_copy(self):
        inst_kwargs = {}
        for attr_name, val in self.inst_kwargs.items():
            if isinstance(val, list):
                inst_kwargs[attr_name] = [v.make_copy() for v in val]
            else:
                inst_kwargs[attr_name] = val.make_copy()
        return self.__class__(context, self.struct, self.attr_name, inst_kwargs)

    def render_content(self):
        for val in self.inst_kwargs.values():
            if not isinstance(val, list):
                val = [val]
            for o in val:
                o.render_content()

    def to_json(self):
        json_content = {}
        for attr_name, val in self.inst_kwargs.items():
            if isinstance(val, list):
                json_content[attr_name] = [v.to_json() for v in val]
            else:
                json_content[attr_name] = val.to_json()
        return json_content

    def __getitem__(self, attr_name):
        return self.inst_kwargs[attr_name]

    def __getattr__(self, attr_name):
        return self.inst_kwargs[attr_name]

    def __str__(self):
        keys = self.struct.primary_keys
        if not keys:
            keys = list(self.struct.attr_types)
        content = ', '.join(str(self[k].content) for k in keys)     # TODO use rendered content
        return f'{self.struct.type_name}({content})'

    def __repr__(self):
        return self.__str__()


class TycoValue:

    _unrendered = object()

    def __init__(self, context, type_name, is_nullable, attr_name, content):
        self.context = context
        self.type_name = type_name
        self.is_nullable = is_nullable
        self.attr_name = attr_name                      # attr_name of the parent TycoInstance
        self.content = content
        self.rendered_value = self._unrendered
        self.parent = None                              # always gets set outside of init

    def make_copy(self):
        return self.__class__(self.context, self.type_name, self.is_nullable, self.attr_name, self.content)

    def render_content(self):
        if self.rendered_value is not self._unrendered:
            return self.rendered_value
        if self.is_nullable and self.content == 'null':
            self.rendered_value = None
            return self.rendered_value
        content = self.content
        if self.type_name == 'str':
            is_literal = content.startswith("'")
            if content[:3] in ("'''", '"""'):
                content = content[3:-3]
                if content.startswith(os.linesep):                 # strip single leading newline
                    content = content[len(os.linesep):]
                print('HERE2', (content,), file=sys.stderr)
            elif content[:1] in ("'", '"'):
                content = content[1:-1]

            if is_literal:
                rendered = content
            else:

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
                    return str(obj.render_content())

                rendered = re.sub(r'\{([\w\.]+)\}', template_render, content)
                rendered = sub_escape_sequences(rendered)

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
        self.rendered_value = rendered
        return rendered

    def to_json(self):
        if isinstance(self.rendered_value, (datetime.date, datetime.time, datetime.datetime)):
            return self.rendered_value.isoformat()
        elif isinstance(self.rendered_value, decimal.Decimal):
            return float(self.rendered_value)
        else:
            return self.rendered_value

    def __str__(self):
        text = f'TycoValue({self.type_name}, {self.content}'
        if self.rendered_value is not self._unrendered:
            text += f', {self.rendered_value}'
        text += ')'
        return text

    def __repr__(self):
        return self.__str__()


def load(path):
    context = TycoContext()
    tyco_lexer = TycoLexer.from_path(context, path)
    tyco_lexer.process()
    context.render_content()
    return context
"""
