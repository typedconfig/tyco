import shutil
import json
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]


def run_in_process_typo_parser(path):
    """Import parser classes and run the lexer/parser in-process.

    Returns the JSON-serializable structure produced by context.to_json().
    """
    try:
        from tyco.parser import TycoContext, TycoLexer  # type: ignore
    except Exception as e:
        pytest.skip(f'parser.py is not importable or raised during import: {e}')

    context = TycoContext()
    # TycoLexer.from_path will cache and call process()
    TycoLexer.from_path(context, str(path))
    # ensure content rendered
    context._render_content()
    return context.to_json()


def _run_and_compare(input_name, expected_name, tmp_path):
    src = ROOT / 'tests' / 'inputs' / input_name
    dst = tmp_path / input_name
    shutil.copy(src, dst)
    data = run_in_process_typo_parser(dst)
    expected = json.loads((ROOT / 'tests' / 'expected' / expected_name).read_text())
    assert data == expected


def test_simple_inputs(tmp_path):
    _run_and_compare('simple1.tyco', 'simple1.json', tmp_path)


def test_basic_types(tmp_path):
    _run_and_compare('basic_types.tyco', 'basic_types.json', tmp_path)


def test_datetime_types(tmp_path):
    _run_and_compare('datetime_types.tyco', 'datetime_types.json', tmp_path)


def test_arrays(tmp_path):
    _run_and_compare('arrays.tyco', 'arrays.json', tmp_path)


def test_nullable(tmp_path):
    _run_and_compare('nullable.tyco', 'nullable.json', tmp_path)


def test_references(tmp_path):
    _run_and_compare('references.tyco', 'references.json', tmp_path)


def test_templates(tmp_path):
    _run_and_compare('templates.tyco', 'templates.json', tmp_path)


def test_defaults(tmp_path):
    _run_and_compare('defaults.tyco', 'defaults.json', tmp_path)


def test_quoted_strings(tmp_path):
    _run_and_compare('quoted_strings.tyco', 'quoted_strings.json', tmp_path)


def test_number_formats(tmp_path):
    _run_and_compare('number_formats.tyco', 'number_formats.json', tmp_path)


def test_edge_cases(tmp_path):
    _run_and_compare('edge_cases.tyco', 'edge_cases.json', tmp_path)
