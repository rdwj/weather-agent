# Contributing to weather-agent

Thank you for your interest in contributing to weather-agent! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/weather-agent.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`

## Development Setup

### Prerequisites

- Python 3.11+
- Podman (not Docker)
- Red Hat OpenShift CLI (oc) for deployment testing

### Local Development

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn src.main:app --reload --port 8000

# Run tests
pytest tests/
pytest --cov=src --cov-report=html

# Linting and formatting
ruff check .
black src/ tests/

# Type checking
mypy src/
```

## Making Changes

1. **Write tests first**: Follow TDD/BDD practices where appropriate
2. **Follow code style**: Use black for formatting and ruff for linting
3. **Add type hints**: Use mypy-compatible type annotations
4. **Test coverage**: Aim for 80%+ code coverage
5. **Document changes**: Update relevant documentation and docstrings

## Testing Standards

- Write unit tests for all new functionality
- Include integration tests for API endpoints
- Test both happy paths and error conditions
- Use descriptive test names that explain what is being tested
- Run the full test suite before submitting a PR

## Pull Request Process

1. Update the README.md or relevant documentation with details of changes
2. Ensure all tests pass and code coverage meets standards
3. Update the CLAUDE.md file if adding new technologies or commands
4. Create a pull request with a clear description of the changes
5. Reference any related issues in your PR description

## Commit Guidelines

- Use clear, descriptive commit messages
- Follow the format: `type: brief description`
- Types: feat, fix, docs, style, refactor, test, chore
- Example: `feat: add weather forecasting endpoint`

## Container Standards

When building containers:

```bash
# Always use Podman with UBI base images
podman build --platform linux/amd64 -t weather-agent:latest -f Containerfile .
```

## Code Review

All submissions require review. We use GitHub pull requests for this purpose. Be responsive to feedback and be prepared to make changes.

## Communication

- GitHub Issues: Bug reports and feature requests
- Pull Requests: Code contributions and discussions

## Questions?

If you have questions, please open an issue:

GitHub: https://github.com/rdwj/weather-agent

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
