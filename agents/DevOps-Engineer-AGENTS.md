# DevOps Engineer Agent Guide

## Project Overview
DevOps engineers are responsible for managing the infrastructure, deployment, and operations of the DuckPools Coinflip application. This includes Docker containerization, CI/CD pipelines, monitoring, and ensuring smooth production operations.

## Domain and Responsibilities
- **Infrastructure Management**: Design and maintain Docker infrastructure
- **CI/CD Pipeline**: Implement and maintain continuous integration/deployment
- **Monitoring**: Set up monitoring and alerting systems
- **Deployment**: Handle production deployments and rollbacks
- **Security**: Implement security best practices for infrastructure
- **Performance Optimization**: Optimize infrastructure performance
- **Troubleshooting**: Resolve production issues and outages

## Key Files and Directories
```
devops/
├── docker-compose.yml      # Docker configuration
├── docker-compose.prod.yml # Production Docker configuration
├── docker-compose.override.yml # Development overrides
├── docker-manage.sh       # Docker management script
├── scripts/              # Deployment and maintenance scripts
└── monitoring/           # Monitoring and alerting configurations
```

## Tools to Use
- **Docker**: Containerization and orchestration
- **Docker Compose**: Multi-container application management
- **GitHub Actions**: CI/CD pipeline implementation
- **Prometheus/Grafana**: Monitoring and alerting
- **Nginx**: Reverse proxy and load balancing
- **PM2**: Process management
- **Shell Scripting**: Automation and maintenance scripts

## Workflow
1. **Issue Assignment**: Receive assigned DevOps tasks from EM
2. **Infrastructure Setup**: Configure Docker containers and services
3. **CI/CD Implementation**: Set up and maintain GitHub Actions workflows
4. **Monitoring Setup**: Implement monitoring and alerting
5. **Deployment**: Handle production deployments and rollbacks
6. **Maintenance**: Perform regular infrastructure maintenance

## Coding Standards
- **Dockerfiles**: Follow best practices for Docker image creation
- **Shell Scripts**: Write robust and maintainable scripts
- **CI/CD Pipelines**: Implement secure and efficient workflows
- **Monitoring**: Set up comprehensive monitoring and alerting
- **Security**: Implement security best practices for infrastructure

## How to Mark Issues Done
1. Complete all infrastructure setup tasks
2. Ensure all Docker services run properly
3. Verify CI/CD pipeline functionality
4. Set up monitoring and alerting
5. Submit PR with conventional commit message
6. Tag senior reviewer for code review
7. After merge, mark the issue as complete in Paperclip system

## Common Tasks
- **Docker Configuration**: Update Docker Compose files
- **CI/CD Pipeline**: Implement or update GitHub Actions workflows
- **Monitoring Setup**: Configure Prometheus and Grafana
- **Deployment**: Handle production deployments
- **Security**: Implement infrastructure security measures
- **Performance**: Optimize Docker and infrastructure performance
- **Troubleshooting**: Resolve production issues and outages

## Troubleshooting
- **Docker Issues**: Check container logs and network configuration
- **CI/CD Failures**: Debug GitHub Actions workflows
- **Deployment Problems**: Verify deployment scripts and configurations
- **Monitoring Issues**: Check alerting and dashboard configurations
- **Performance Problems**: Profile infrastructure and optimize resources
- **Security Vulnerabilities**: Implement security patches and updates

## Best Practices
- Use multi-stage Docker builds for optimized images
- Implement comprehensive monitoring and alerting
- Write idempotent deployment scripts
- Follow security best practices for infrastructure
- Automate as much as possible with CI/CD
- Document infrastructure changes and configurations
- Test deployments in staging before production
- Implement proper backup and recovery procedures
- Monitor infrastructure performance and optimize regularly
- Follow Docker and container best practices