# QuantLab AI — Engineering Standards

> **The Rules of the Road**  
> Version 1.0 | Last Updated: July 2026

---

## Code Quality Standards

### File Size Limits
| Language | Max Lines per File | Preferred Max |
|----------|-------------------|---------------|
| Python | 500 | 200-300 |
| TypeScript | 400 | 150-250 |
| SQL | 200 | 50-100 |
| YAML/JSON | 200 | 50-100 |
| Markdown | 500 | 100-300 |

### Function/Method Size
| Metric | Maximum | Preferred |
|--------|---------|-----------|
| Lines per function | 50 | 10-25 |
| Parameters per function | 5 | 0-3 |
| Nesting depth | 4 | 1-2 |
| Return points | 3 | 1 |

### Class Standards
| Metric | Maximum | Preferred |
|--------|---------|-----------|
| Methods per class | 15 | 5-10 |
| Instance variables | 10 | 3-7 |
| Inheritance depth | 3 | 0-1 |

---

## Testing Standards

### Coverage Requirements
| Layer | Minimum Coverage | Target |
|-------|-----------------|--------|
| Domain (packages/core) | 95% | 100% |
| Application (services/*) | 90% | 95% |
| Interface (apps/*) | 80% | 90% |
| Infrastructure (plugins/*) | 70% | 85% |

### Test Types
| Type | Responsibility | Speed | Frequency |
|------|---------------|-------|-----------|
| Unit | Single function/class | < 100ms | Every save |
| Integration | Service boundaries | < 1s | Every commit |
| E2E | Full workflow | < 5min | Every PR |
| AI | Agent behavior | < 10min | Daily |

---

## Documentation Standards

### Required Documentation
| Component | Minimum Docs | Update Frequency |
|-----------|-------------|------------------|
| Public API | Docstrings, type hints | Per change |
| Service | README, architecture | Per major change |
| Decision | ADR | Per decision |
| Strategy | Research report | Per strategy |
| Database | Schema diagram | Per migration |

### Docstring Format (Python)
```python
def function_name(param1: str, param2: int) -> bool:
    \"\"\"Brief description.

    Detailed description if needed.

    Args:
        param1: Description
        param2: Description

    Returns:
        Description of return value

    Raises:
        ValueError: When ...

    Examples:
        >>> function_name("test", 42)
        True
    \"\"\"
```

---

## Naming Conventions

### Python
| Element | Convention | Example |
|---------|-----------|---------|
| File names | snake_case | data_pipeline.py |
| Class names | PascalCase | DataPipeline |
| Functions | snake_case | process_data() |
| Variables | snake_case | market_data |
| Constants | UPPER_CASE | MAX_RETRY_COUNT |
| Private | _prefix | _internal_method |
| Protected | single_prefix | _protected |
| Private (module) | __prefix | __module_private |

### TypeScript
| Element | Convention | Example |
|---------|-----------|---------|
| File names | kebab-case | data-pipeline.ts |
| Class names | PascalCase | DataPipeline |
| Functions | camelCase | processData() |
| Variables | camelCase | marketData |
| Interfaces | PascalCase | IDataPipeline |
| Types | PascalCase | MarketDataType |

---

## Git Standards

### Commit Messages
```
type(scope): brief description

Optional detailed description.

- Bullet points for details
- Reference issues: #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

### Branch Naming
| Type | Format | Example |
|------|--------|---------|
| Feature | feature/description | feature/data-pipeline |
| Bug fix | fix/description | fix/null-pointer |
| Research | research/description | research/mean-reversion |
| Docs | docs/description | docs/api-spec |

---

## Code Review Standards

### Reviewer Checklist
- [ ] Code follows standards
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No security issues
- [ ] Error handling is appropriate
- [ ] Logging is sufficient
- [ ] Performance is considered
- [ ] No TODO/FIXME without issue reference
- [ ] Types are correct (mypy/flake8 happy)

### PR Size Limits
| Size | Lines Changed | Review Required |
|------|--------------|-----------------|
| Small | < 100 | 1 reviewer |
| Medium | 100-500 | 2 reviewers |
| Large | 500+ | Break into smaller PRs |

---

## Performance Standards

| Metric | Target | Alert |
|--------|--------|-------|
| API response time (p95) | < 200ms | > 500ms |
| Backtest speed | > 10,000 bars/sec | < 1,000 bars/sec |
| Query time (p95) | < 100ms | > 500ms |
| Memory per service | < 512MB | > 1GB |
| Startup time | < 10s | > 30s |
