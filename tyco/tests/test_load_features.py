import os
import json
import shutil
import tempfile
from pathlib import Path
import pytest

from tyco import load, loads

ROOT = Path(__file__).resolve().parents[1]


def test_loads_basic():
    """Test loads() function with basic tyco content."""
    content = """
str environment: production
int port: 8080

Server:
 *str name:
  int port:
  - web1, 80
  - api1, 3000
"""
    context = loads(content)
    data = context.to_json()
    
    assert data['environment'] == 'production'
    assert data['port'] == 8080
    assert len(data['Server']) == 2
    assert data['Server'][0]['name'] == 'web1'
    assert data['Server'][0]['port'] == 80


def test_loads_empty_content():
    """Test loads() with empty content."""
    context = loads("")
    data = context.to_json()
    assert data == {}


def test_loads_with_templates():
    """Test loads() with template expansion."""
    content = """
str env: staging
str region: us-west-2

Server:
 *str name:
  str env:
  str region:
  str hostname:
  - web1, staging, us-west-2, {name}-{env}-{region}
"""
    context = loads(content)
    data = context.to_json()
    
    assert data['Server'][0]['hostname'] == 'web1-staging-us-west-2'


def test_load_directory_structure(tmp_path):
    """Test loading an entire directory with multiple .tyco files."""
    # Create directory structure
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create main config file
    main_config = config_dir / "main.tyco"
    main_config.write_text("""
str environment: production
str region: us-east-1

Database:
 *str name:
  str host:
  int port:
  - primary, db1.example.com, 5432
""")
    
    # Create servers config file
    servers_config = config_dir / "servers.tyco"
    servers_config.write_text("""
Server:
 *str name:
  Database db:
  str region:
  - web1, Database(primary), us-east-1
  - api1, Database(primary), us-west-2
""")
    
    # Create subdirectory with another config
    subdir = config_dir / "services"
    subdir.mkdir()
    service_config = subdir / "monitoring.tyco"
    service_config.write_text("""
Monitor:
 *str service:
  str endpoint:
  - prometheus, /metrics
  - grafana, /api/health
""")
    
    # Load the entire directory
    context = load(str(config_dir))
    data = context.to_json()
    
    # Verify all files were loaded
    assert data['environment'] == 'production'
    assert data['region'] == 'us-east-1'
    assert len(data['Database']) == 1
    assert len(data['Server']) == 2
    assert len(data['Monitor']) == 2
    
    # Verify references work across files
    assert data['Server'][0]['db']['name'] == 'primary'
    assert data['Server'][0]['db']['host'] == 'db1.example.com'


def test_load_directory_with_python_validators(tmp_path):
    """Test loading directory with Python validator modules."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create tyco config file
    config_file = config_dir / "app.tyco"
    config_file.write_text("""
User:
 *str username:
  str email:
  int age:
  - alice, alice@example.com, 30
  - bob, bob@invalid-email, 25
  - charlie, charlie@example.com, -5
""")
    
    # Create corresponding Python validator
    validator_file = config_dir / "app.py"
    validator_file.write_text("""
import re
from tyco.parser import Struct

class User(Struct):
    def validate(self):
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.email):
            raise ValueError(f"Invalid email format: {self.email}")
        
        # Validate age is positive
        if self.age < 0:
            raise ValueError(f"Age must be positive: {self.age}")
""")
    
    # Load the directory - this should trigger validation
    context = load(str(config_dir))
    
    # Get objects (which triggers validation)
    with pytest.raises(ValueError, match="Invalid email format"):
        objects = context.get_objects()


def test_load_directory_recursive_structure(tmp_path):
    """Test loading deeply nested directory structure."""
    # Create nested structure: config/env/prod/database.tyco
    base_dir = tmp_path / "config"
    env_dir = base_dir / "env" 
    prod_dir = env_dir / "prod"
    prod_dir.mkdir(parents=True)
    
    # Files at different levels
    (base_dir / "globals.tyco").write_text("str app_name: MyApp\n")
    (env_dir / "common.tyco").write_text("int timeout: 30\n")
    (prod_dir / "database.tyco").write_text("""
Database:
 *str name:
  str host:
  - main, prod-db.example.com
""")
    
    context = load(str(base_dir))
    data = context.to_json()
    
    assert data['app_name'] == 'MyApp'
    assert data['timeout'] == 30
    assert data['Database'][0]['name'] == 'main'


def test_load_single_file_vs_directory_compatibility(tmp_path):
    """Test that load() works the same for single files as before."""
    # Create a single file
    config_file = tmp_path / "single.tyco"
    config_file.write_text("""
str version: 1.0.0

Service:
 *str name:
  int replicas:
  - web, 3
  - api, 2
""")
    
    # Load as single file
    context = load(str(config_file))
    data = context.to_json()
    
    assert data['version'] == '1.0.0'
    assert len(data['Service']) == 2
    assert data['Service'][0]['replicas'] == 3


def test_python_validator_import_failure_graceful(tmp_path):
    """Test that invalid Python validators don't break loading."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create tyco file
    (config_dir / "test.tyco").write_text("""
Item:
 *str name:
  - item1
""")
    
    # Create invalid Python file
    (config_dir / "test.py").write_text("""
# This has syntax errors
def invalid_syntax(
    missing_closing_paren
""")
    
    # Should still load successfully, just without validation
    context = load(str(config_dir))
    data = context.to_json()
    assert len(data['Item']) == 1


def test_load_directory_no_tyco_files(tmp_path):
    """Test loading directory with no .tyco files."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    
    # Create some non-tyco files
    (empty_dir / "readme.txt").write_text("Not a tyco file")
    (empty_dir / "config.json").write_text('{"key": "value"}')
    
    context = load(str(empty_dir))
    data = context.to_json()
    assert data == {}


def test_loads_vs_load_consistency(tmp_path):
    """Test that loads() and load() produce identical results for same content."""
    content = """
str app_name: MyApp

Config:
 *str env:
  str app:
  str full_name:
  - env: development, app: MyApp, full_name: {app}-{env}
  - env: production, app: MyApp, full_name: {app}-{env}
"""
    
    # Test with loads()
    context_loads = loads(content)
    data_loads = context_loads.to_json()
    
    # Test with load() using temp file
    temp_file = tmp_path / "test.tyco"
    temp_file.write_text(content)
    context_load = load(str(temp_file))
    data_load = context_load.to_json()
    
    assert data_loads == data_load


def test_directory_load_with_include_directives(tmp_path):
    """Test directory loading where files use #include directives."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create base definitions
    (config_dir / "base.tyco").write_text("""
Database:
 *str name:
  str host:
  int port:
  - primary, db.example.com, 5432
""")
    
    # Create file that includes base
    (config_dir / "services.tyco").write_text("""
#include base.tyco

Service:
 *str name:
  Database db:
  - web-service, Database(primary)
""")
    
    context = load(str(config_dir))
    data = context.to_json()
    
    # Should work even though base.tyco gets loaded twice
    assert data['Service'][0]['db']['name'] == 'primary'
    assert data['Service'][0]['db']['port'] == 5432


def test_python_validator_with_custom_validation(tmp_path):
    """Test Python validator with custom validation logic."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create config with port numbers
    (config_dir / "network.tyco").write_text("""
Port:
 *str name:
  int number:
  str protocol:
  - http, 80, tcp
  - https, 443, tcp
  - ssh, 22, tcp
  - invalid, 70000, tcp
""")
    
    # Create validator that checks port ranges
    (config_dir / "network.py").write_text("""
from tyco.parser import Struct

class Port(Struct):
    def validate(self):
        if not (1 <= self.number <= 65535):
            raise ValueError(f"Port number {self.number} out of valid range (1-65535)")
        if self.protocol not in ['tcp', 'udp']:
            raise ValueError(f"Invalid protocol: {self.protocol}")
""")
    
    context = load(str(config_dir))
    
    # Should fail validation on the invalid port
    with pytest.raises(ValueError, match="Port number 70000 out of valid range"):
        objects = context.get_objects()