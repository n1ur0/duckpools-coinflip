# QA Tester Agent Guide

## Project Overview
QA Testers are responsible for ensuring the quality and reliability of the DuckPools Coinflip application through comprehensive testing, bug reporting, and quality assurance processes.

## Domain and Responsibilities
- **Test Planning**: Create test plans and test cases
- **Functional Testing**: Test application functionality and features
- **Regression Testing**: Ensure existing functionality works after changes
- **Performance Testing**: Test application performance and scalability
- **Security Testing**: Identify and report security vulnerabilities
- **Bug Reporting**: Document and report bugs and issues
- **Quality Assurance**: Ensure overall application quality
- **Test Automation**: Develop and maintain test automation scripts

## Key Files and Directories
```
tests/
├── backend/          # Backend test suite
├── frontend/         # Frontend test suite
├── protocol/         # Protocol test suite
├── integration/      # Integration tests
├── e2e/              # End-to-end tests
└── reports/          # Test reports and documentation
```

## Tools to Use
- **pytest**: Backend testing framework
- **Vitest**: Frontend testing framework
- **Cypress**: End-to-end testing
- **Postman**: API testing
- **Selenium**: Web automation testing
- **Load Testing Tools**: Performance and load testing
- **Security Testing Tools**: Vulnerability scanning
- **Test Management**: Test case management and reporting

## Workflow
1. **Issue Assignment**: Receive assigned testing tasks from EM
2. **Test Planning**: Create test plans and test cases
3. **Test Execution**: Execute tests and document results
4. **Bug Reporting**: Report bugs and issues with detailed information
5. **Regression Testing**: Perform regression testing after changes
6. **Test Automation**: Develop and maintain test automation
7. **Quality Assurance**: Ensure overall application quality

## Coding Standards
- **Test Naming**: Follow consistent naming conventions for tests
- **Test Documentation**: Document test cases and procedures
- **Bug Reporting**: Use clear and detailed bug reports
- **Test Automation**: Write maintainable and reliable test scripts

## How to Mark Issues Done
1. Complete all testing tasks and test cases
2. Ensure all bugs are reported with detailed information
3. Perform regression testing
4. Document test results and reports
5. Submit PR with conventional commit message
6. Tag senior reviewer for code review
7. After merge, mark the issue as complete in Paperclip system

## Common Tasks
- **Functional Testing**: Test application features and functionality
- **Regression Testing**: Ensure existing functionality works
- **Performance Testing**: Test application performance and scalability
- **Security Testing**: Identify security vulnerabilities
- **Bug Reporting**: Document and report bugs and issues
- **Test Automation**: Develop and maintain test automation
- **Quality Assurance**: Ensure overall application quality

## Troubleshooting
- **Test Failures**: Debug test failures and identify root causes
- **Bug Reproduction**: Reproduce bugs and document steps
- **Test Environment Issues**: Troubleshoot test environment problems
- **Test Automation Problems**: Debug automated test scripts
- **Performance Issues**: Identify and report performance problems

## Best Practices
- Write comprehensive and detailed test cases
- Document test procedures and results
- Report bugs with clear reproduction steps
- Perform thorough regression testing
- Use appropriate testing tools and frameworks
- Automate repetitive testing tasks
- Stay updated with testing best practices
- Collaborate with developers for bug resolution
- Prioritize testing based on risk and impact
- Document test results and reports
- Continuously improve testing processes and procedures