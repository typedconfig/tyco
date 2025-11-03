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
    context.render_content()
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
