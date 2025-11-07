# Tyco Python

[![PyPI version](https://badge.fury.io/py/tyco.svg)](https://badge.fury.io/py/tyco)
[![Python Version](https://img.shields.io/pypi/pyversions/tyco.svg)](https://pypi.org/project/tyco/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for parsing and working with Tyco configuration files - a modern, type-safe configuration language designed for clarity and flexibility.

## 🚀 Quick Start

### Installation

```bash
pip install tyco
```

### Basic Usage

```python
import tyco

# Parse a Tyco configuration file
config = tyco.load('config.tyco')

# Access configuration values
database_url = config.database.url
port = config.server.port
features = config.features  # Array access
```

### Example Tyco File

```tyco
# Global configuration
environment = "production"
debug = false

# Database configuration
database {
    host = "localhost"
    port = 5432
    name = "myapp"
    url = "postgresql://{database.host}:{database.port}/{database.name}"
}

# Server configuration
server {
    port = 8080
    workers = 4
    timeout = 30.0
}

# Feature flags
features = ["auth", "analytics", "caching"]
```

## ✨ Features

### 🎯 **Type Safety**
- **Strong Typing**: Automatic type inference and validation
- **Runtime Checks**: Type safety enforced during parsing
- **Clear Error Messages**: Helpful parsing errors with line numbers

### 🔧 **Template System**
- **Variable Substitution**: Use `{variable}` syntax for dynamic values
- **Nested References**: Support for complex variable relationships
- **Scope Resolution**: Automatic resolution of global and local variables

### 🏗️ **Flexible Structure**
- **Nested Objects**: Unlimited nesting depth for complex configurations
- **Arrays**: Support for homogeneous and mixed-type arrays
- **Comments**: Full comment support for documentation

### 🌐 **Cross-Platform**
- **Pure Python**: No external dependencies
- **Python 3.8+**: Modern Python support
- **All Operating Systems**: Linux, macOS, Windows

## 📖 Language Features

### Data Types

```tyco
# Strings
name = "MyApp"
description = """
Multi-line string
with proper formatting
"""

# Numbers
port = 8080
timeout = 30.5
precision = 1.23e-4

# Booleans
debug = true
production = false

# Arrays
servers = ["web1", "web2", "web3"]
ports = [80, 443, 8080]
mixed = ["string", 42, true]
```

### Object Structures

```tyco
# Simple objects
database {
    host = "localhost"
    port = 5432
}

# Nested objects
app {
    server {
        host = "0.0.0.0"
        port = 8080
    }
    
    cache {
        redis {
            host = "redis.local"
            port = 6379
        }
    }
}
```

### Template Variables

```tyco
# Global variables for reuse
base_url = "https://api.example.com"
version = "v2"

# Template substitution
api {
    endpoint = "{base_url}/{version}/users"
    health_check = "{base_url}/health"
}

# Nested variable references
database {
    host = "db.example.com"
    port = 5432
    connection_string = "postgresql://{database.host}:{database.port}/myapp"
}
```

## 🔧 API Reference

### Core Functions

#### `tyco.load(filepath)`
Load and parse a Tyco configuration file.

```python
config = tyco.load('app.tyco')
```

**Parameters:**
- `filepath` (str | Path): Path to the Tyco configuration file

**Returns:** Parsed configuration object with dot notation access

#### `tyco.loads(content)`
Parse Tyco configuration from a string.

```python
config_text = """
app_name = "MyApp"
port = 8080
"""
config = tyco.loads(config_text)
```

**Parameters:**
- `content` (str): Tyco configuration content as string

**Returns:** Parsed configuration object

### Configuration Access

```python
config = tyco.load('config.tyco')

# Dot notation access
app_name = config.app_name
db_host = config.database.host

# Dictionary-style access
port = config['server']['port']

# Array access
first_server = config.servers[0]

# Check if key exists
if hasattr(config, 'optional_setting'):
    value = config.optional_setting
```

## 🧪 Testing

The library includes comprehensive tests covering all language features:

```bash
# Run tests
python -m pytest

# Run with coverage
python -m pytest --cov=tyco --cov-report=html
```

### Test Coverage
- ✅ **Parsing**: All data types, structures, and syntax variants
- ✅ **Templates**: Variable substitution and scope resolution  
- ✅ **Error Handling**: Invalid syntax and type mismatches
- ✅ **Edge Cases**: Empty files, complex nesting, special characters

## 📁 Project Structure

```
tyco-python/
├── tyco/
│   ├── __init__.py          # Main API exports
│   ├── parser.py            # Core parsing logic
│   └── tests/
│       ├── __init__.py
│       ├── test_parser.py   # Parser functionality tests
│       └── test_load_features.py  # Load feature tests
├── pyproject.toml           # Project configuration
├── README.md               # This file
└── LICENSE                 # MIT License
```

## 🌟 Examples

### Web Application Configuration

```tyco
# app.tyco
environment = "production"
debug = false

database {
    host = "localhost"
    port = 5432
    name = "webapp"
    pool_size = 20
    url = "postgresql://{database.host}:{database.port}/{database.name}"
}

server {
    host = "0.0.0.0" 
    port = 8080
    workers = 4
}

redis {
    host = "localhost"
    port = 6379
    db = 0
}

features = ["authentication", "caching", "analytics"]
```

```python
# app.py
import tyco

config = tyco.load('app.tyco')

# Use configuration
print(f"Starting server on {config.server.host}:{config.server.port}")
print(f"Database URL: {config.database.url}")
print(f"Features enabled: {', '.join(config.features)}")
```

### Microservices Configuration

```tyco
# services.tyco
base_domain = "internal.company.com"
common_timeout = 30.0

services {
    auth {
        host = "auth.{base_domain}"
        port = 8001
        timeout = {common_timeout}
    }
    
    user {
        host = "user.{base_domain}"  
        port = 8002
        timeout = {common_timeout}
    }
    
    payment {
        host = "payment.{base_domain}"
        port = 8003
        timeout = 60.0  # Override for longer operations
    }
}

load_balancer {
    upstream_servers = [
        "{services.auth.host}:{services.auth.port}",
        "{services.user.host}:{services.user.port}",
        "{services.payment.host}:{services.payment.port}"
    ]
}
```

## 🤝 Contributing

We welcome contributions! The parser implementation follows these principles:

1. **Clarity**: Code should be readable and well-documented
2. **Reliability**: Comprehensive test coverage for all features  
3. **Performance**: Efficient parsing for large configuration files
4. **Compatibility**: Support for Python 3.8+ across all platforms

### Development Setup

```bash
# Clone the repository
git clone https://github.com/typedconfig/tyco-python.git
cd tyco-python

# Install development dependencies
pip install -e .
pip install pytest pytest-cov

# Run tests
python -m pytest
```

## 📋 Requirements

- **Python**: 3.8 or higher
- **Dependencies**: None (pure Python implementation)
- **Operating Systems**: Linux, macOS, Windows

## 🔗 Related Projects

- **[Tyco C++](https://github.com/typedconfig/tyco-cpp)**: C++ implementation with hash map architecture
- **[Tyco Web](https://github.com/typedconfig/web)**: Interactive playground and language documentation
- **[Language Specification](https://typedconfig.io)**: Complete Tyco language reference

## 📄 License

MIT License - see the [LICENSE](LICENSE) file for details.

## 🌍 Learn More

- **Website**: [https://typedconfig.io](https://typedconfig.io)
- **Documentation**: [Language specification and examples](https://typedconfig.io)
- **Repository**: [https://github.com/typedconfig/tyco-python](https://github.com/typedconfig/tyco-python)
