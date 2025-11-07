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
environment = config.environment
servers = config.Server  # Access struct instances
database_url = config.Database[0].connection_string
```

### Example Tyco File

```tyco
# Global configuration with type annotations
str environment: production
bool debug: false
int timeout: 30

# Database configuration struct
Database:
 *str name:           # Required field (*)
  str host:
  int port:
  str connection_string:
  # Instances
  - primary, localhost, 5432, postgresql://localhost:5432/myapp
  - replica, replica-host, 5432, postgresql://replica-host:5432/myapp

# Server configuration struct  
Server:
 *str name:
  int port:
  str host:
  ?str description:    # Optional field (?)
  # Server instances
  - web1, 8080, web1.example.com, "Primary web server"
  - api1, 3000, api1.example.com
  - worker1, 9000, worker1.example.com, "Background worker"

# Feature flags array
str[] features: [auth, analytics, caching]
```

## ✨ Features

### 🎯 **Type Safety**
- **Strong Type Annotations**: `str`, `int`, `float`, `bool`, `date`, `time`, `datetime`
- **Array Types**: `int[]`, `str[]`, etc. for typed arrays
- **Nullable Types**: `?str`, `?int` for optional fields
- **Runtime Validation**: Type safety enforced during parsing

### 🏗️ **Structured Configuration**
- **Struct Definitions**: Define reusable configuration structures
- **Required/Optional Fields**: `*` for required, `?` for optional fields  
- **Multiple Instances**: Create multiple instances of the same struct
- **Nested References**: Access fields from other structs

### 🔧 **Template System**
- **Variable Substitution**: Use `{variable}` syntax for dynamic values
- **Nested References**: `{struct.field}` for complex relationships
- **Template Expansion**: Automatic resolution during parsing

### 🌐 **Cross-Platform**
- **Pure Python**: No external dependencies
- **Python 3.8+**: Modern Python support
- **All Operating Systems**: Linux, macOS, Windows

## 📖 Language Features

### Type Annotations

```tyco
# Basic types
str app_name: MyApplication
int port: 8080
float timeout: 30.5
bool enabled: true

# Date and time types
date launch_date: 2025-01-01
time start_time: 09:00:00
datetime created_at: 2025-01-01 09:00:00Z

# Array types
str[] environments: [dev, staging, prod]
int[] ports: [80, 443, 8080]

# Nullable types
?str description: null
?int backup_port: 8081
```

### Struct Definitions

```tyco
# Define a struct with required (*) and optional (?) fields
User:
 *str username:        # Required field
  str email:
 ?str full_name:       # Optional field
 ?int age: 25          # Optional with default
  bool active: true    # Default value
  # Create instances
  - admin, admin@example.com, "Administrator", 35, true
  - user1, user1@example.com, "John Doe", 28
  - guest, guest@example.com  # Uses defaults for optional fields

# Nested struct references
Project:
 *str name:
  User owner:          # Reference to User struct
  str[] tags:
  - webapp, User(admin), [frontend, react]
  - api, User(user1), [backend, python, fastapi]
```

### Template Variables

```tyco
# Global variables for reuse
str environment: production
str region: us-east-1
str domain: example.com

# Template expansion in values
str api_url: https://api-{environment}-{region}.{domain}
str log_path: /var/log/{environment}

# Templates in struct instances
Service:
 *str name:
  str url:
  str log_file:
  - auth, https://{name}-{environment}.{domain}, /logs/{environment}/{name}.log
  - users, https://{name}-{environment}.{domain}, /logs/{environment}/{name}.log
```

### Arrays and Collections

```tyco
# Typed arrays
str[] allowed_origins: [
  https://app.example.com,
  https://admin.example.com
]

int[] fibonacci: [1, 1, 2, 3, 5, 8, 13]

# Mixed arrays with struct instances
Server:
 *str name:
  int cores:
  bool active:
  - web1, 4, true
  - web2, 8, false
  - db1, 16, true

# Array references
str[] server_names: [web1, web2, db1]
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

**Returns:** Parsed configuration object with attribute access

#### `tyco.loads(content)`
Parse Tyco configuration from a string.

```python
config_text = """
str app_name: MyApp
int port: 8080
"""
config = tyco.loads(config_text)
```

**Parameters:**
- `content` (str): Tyco configuration content as string

**Returns:** Parsed configuration object

### Configuration Access

```python
config = tyco.load('config.tyco')

# Access global variables
app_name = config.app_name
port = config.port

# Access struct instances (returns list)
servers = config.Server  # All Server instances
first_server = config.Server[0]  # First server
server_names = [s.name for s in config.Server]  # Extract names

# Access specific fields
db_host = config.Database[0].host
api_url = config.Service[0].url  # Template expanded
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
- ✅ **Type System**: All basic types, arrays, nullable types
- ✅ **Structs**: Required/optional fields, instances, defaults
- ✅ **Templates**: Variable substitution and nested references
- ✅ **Edge Cases**: Complex nesting, special characters, error handling

## 📁 Project Structure

```
tyco-python/
├── tyco/
│   ├── __init__.py          # Main API exports
│   ├── parser.py            # Core parsing logic and classes
│   └── tests/
│       ├── __init__.py
│       ├── test_parser.py   # Parser functionality tests
│       ├── test_load_features.py  # Load feature tests
│       ├── inputs/          # Test Tyco files
│       └── expected/        # Expected JSON outputs
├── pyproject.toml           # Project configuration
├── README.md               # This file
└── LICENSE                 # MIT License
```

## �� Examples

### Web Application Configuration

```tyco
# app.tyco
str environment: production
bool debug: false
str secret_key: your-secret-key-here

# Database configuration
Database:
 *str name:
  str host:
  int port:
  str user:
  str connection_string:
  - main, db.example.com, 5432, webapp_user, postgresql://{user}@{host}:{port}/{name}
  - cache, cache.example.com, 6379, cache_user, redis://{host}:{port}

# Application servers  
Server:
 *str name:
  str host:
  int port:
  int workers:
  ?str description:
  - web, 0.0.0.0, 8080, 4, "Main web server"
  - api, 0.0.0.0, 8081, 2, "API server"
  - worker, 127.0.0.1, 8082, 1

# Feature flags
str[] enabled_features: [authentication, caching, analytics]
```

```python
# app.py
import tyco

config = tyco.load('app.tyco')

# Use configuration
print(f"Environment: {config.environment}")
print(f"Debug mode: {config.debug}")

# Database connection
db = config.Database[0]  # Get first (main) database
print(f"Database URL: {db.connection_string}")

# Server configuration
for server in config.Server:
    print(f"Server {server.name}: {server.host}:{server.port} ({server.workers} workers)")

# Feature flags
if 'authentication' in config.enabled_features:
    print("Authentication is enabled")
```

### Microservices Configuration

```tyco
# services.tyco
str environment: staging
str base_domain: internal.company.com
int default_timeout: 30

# Service definitions
Service:
 *str name:
  str host:
  int port:
  int timeout:
  str health_endpoint:
  - auth, auth.{base_domain}, 8001, {default_timeout}, /health
  - users, users.{base_domain}, 8002, {default_timeout}, /api/health  
  - payments, payments.{base_domain}, 8003, 60, /status
  - notifications, notifications.{base_domain}, 8004, {default_timeout}, /ping

# Load balancer configuration  
LoadBalancer:
 *str name:
  str[] upstream_servers:
  str algorithm:
  - main, [
      {Service[0].host}:{Service[0].port},
      {Service[1].host}:{Service[1].port},
      {Service[2].host}:{Service[2].port}
    ], round_robin

# Monitoring configuration
Monitor:
 *str service_name:
  str endpoint:
  int check_interval:
  - auth_monitor, https://{Service[0].host}:{Service[0].port}{Service[0].health_endpoint}, 30
  - user_monitor, https://{Service[1].host}:{Service[1].port}{Service[1].health_endpoint}, 30
```

## 🤝 Contributing

We welcome contributions! The parser implementation follows these principles:

1. **Type Safety**: Strong type checking and validation
2. **Clarity**: Clean, readable configuration syntax
3. **Performance**: Efficient parsing for large configuration files
4. **Reliability**: Comprehensive test coverage for all features

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
