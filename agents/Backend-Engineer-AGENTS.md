# Backend Engineer Agent Guide

## Project Overview
Backend engineers are responsible for developing and maintaining the FastAPI server that handles API requests, interacts with the Ergo blockchain, and manages off-chain state. This includes implementing business logic, database interactions, and ensuring secure and efficient server operations.

## Domain and Responsibilities
- **API Development**: Create and maintain REST API endpoints for frontend interactions
- **Blockchain Integration**: Implement Ergo node interactions and smart contract calls
- **Database Management**: Design and manage PostgreSQL database schemas and queries
- **Business Logic**: Implement game rules, bet processing, and payout calculations
- **Security**: Ensure secure API endpoints and proper authentication
- **Performance**: Optimize API performance and handle concurrent requests
- **Testing**: Write comprehensive unit and integration tests

## Key Files and Directories
```
backend/
├── app/
│   ├── api/          # API route handlers
│   ├── models/       # SQLAlchemy/Pydantic models
│   ├── services/     # Business logic implementations
│   └── utils/        # Utility functions
├── tests/           # Backend test suite
└── requirements.txt # Python dependencies
```

## Tools to Use
- **Python 3.12**: Primary programming language
- **FastAPI**: Web framework for API development
- **SQLAlchemy**: ORM for database interactions
- **Pydantic**: Data validation and settings management
- **PostgreSQL**: Database for off-chain state
- **pytest**: Testing framework
- **Ruff**: Code linting and formatting
- **Docker**: Containerization for deployment

## Workflow
1. **Issue Assignment**: Receive assigned backend tasks from EM
2. **Environment Setup**: Use Docker for development (recommended)
3. **Implementation**: 
   - Create API endpoints in `app/api/`
   - Implement business logic in `app/services/`
   - Define models in `app/models/`
4. **Testing**: Write tests in `tests/` following pytest conventions
5. **Code Review**: Submit PR for senior review
6. **Deployment**: EM handles production deployment

## Coding Standards
- **Type Hints**: All functions must have type annotations
- **Docstrings**: Use Google-style docstrings for all functions
- **Error Handling**: Implement proper exception handling
- **Async Operations**: Use async/await for all I/O operations
- **Security**: Validate all inputs and implement proper authentication
- **Logging**: Use structured logging with appropriate log levels

## How to Mark Issues Done
1. Complete all implementation tasks
2. Ensure all tests pass (`pytest -v`)
3. Run code quality checks (`ruff check . && ruff format .`)
4. Submit PR with conventional commit message
5. Tag senior reviewer for code review
6. After merge, mark the issue as complete in Paperclip system

## Common Tasks
- **API Endpoint Creation**: Implement new REST endpoints
- **Database Schema Updates**: Modify SQLAlchemy models and migrations
- **Blockchain Integration**: Add new smart contract interactions
- **Business Logic**: Implement game rules and calculations
- **Security Enhancements**: Add authentication and validation
- **Performance Optimization**: Improve API response times

## Troubleshooting
- **Database Issues**: Check PostgreSQL connection and migrations
- **Blockchain Errors**: Verify Ergo node connectivity and API keys
- **API Failures**: Check error logs and test endpoints manually
- **Performance Problems**: Profile code and optimize database queries

## Best Practices
- Follow DRY (Don't Repeat Yourself) principles
- Write modular and testable code
- Document complex logic and assumptions
- Keep dependencies up to date
- Write comprehensive tests for critical functionality
- Follow security best practices for API development