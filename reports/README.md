# Team Status Reporting System

This system implements the reporting chain workflow described in MAT-153 for Executive Managers. It provides automated task monitoring, report generation, and leadership communication.

## Overview

The Team Status Reporting System enables:

1. **Task Monitoring**: Track task completion and collect run outputs
2. **Report Generation**: Automatically compile summary reports when all sub-tasks are complete
3. **Issue Integration**: Post reports as comments on parent issues
4. **Leadership Reporting**: Create TEAM STATUS REPORT issues for CEO review
5. **CEO Notification**: Alert CEO to review critical reports

## Components

### 1. Executive Manager Prompt Template
- `executive_manager_prompt_template.md`: Comprehensive template guiding EMs through the reporting chain
- Includes workflow, report structure, and implementation guidelines

### 2. Team Status Reporter
- `team_status_reporter.py`: Core reporting logic implementation
- Handles task monitoring, report compilation, and CEO notifications
- Follows the structured reporting format from the template

### 3. API Service
- `api_server.py`: FastAPI service for integrating with Paperclip
- Provides endpoints for task notifications and report generation
- Supports CORS for web integration

## Usage

### Running the API Service
```bash
cd reports
python api_server.py
```

The API will be available at `http://localhost:8001`

### Using the Reporter
```python
from team_status_reporter import TeamStatusReporter

# Initialize reporter
reporter = TeamStatusReporter()

# Run reporting cycle for a parent issue
report = reporter.run_reporting_cycle(parent_issue_id="your-issue-id")
```

### API Endpoints

#### Task Completion Notification
```bash
POST /api/tasks/complete
{
    "task_id": "task-123",
    "issue_id": "parent-issue-456",
    "run_output": "Task completed successfully",
    "metrics": {"status": "success"},
    "errors": [],
    "status": "completed"
}
```

#### Generate Report
```bash
POST /api/reports/generate
{
    "issue_id": "parent-issue-456",
    "task_results": [
        {
            "task_id": "task-123",
            "issue_id": "parent-issue-456",
            "run_output": "Task completed successfully",
            "metrics": {"status": "success"},
            "errors": [],
            "status": "completed"
        }
    ]
}
```

## Report Structure

### Executive Summary
- Overall team status and performance metrics
- Key achievements and milestones reached
- Critical issues and their impact on objectives

### Detailed Findings
- Task-by-task results and outputs
- Performance metrics and KPIs
- Quality indicators and compliance status

### Blockers and Risks
- Current blockers affecting team velocity
- Risk assessment and impact analysis
- Mitigation strategies and timelines

### Recommendations
- Strategic recommendations for leadership
- Resource allocation suggestions
- Process improvements and optimizations

### Next Steps
- Immediate actions required
- Long-term planning considerations
- Follow-up items and responsibilities

## Integration with Paperclip

The system is designed to integrate with the Paperclip API for:

1. **Issue Management**: Create and update issues
2. **Task Tracking**: Monitor task completion status
3. **Comment Posting**: Post reports as comments on parent issues
4. **CEO Assignment**: Assign TEAM STATUS REPORT issues to CEO

## Configuration

### Environment Variables
- `API_BASE_URL`: Base URL for Paperclip API (default: http://127.0.0.1:3100)
- `CEO_AGENT_ID`: ID of the CEO agent (default: ceo)
- `TEAM_NAME`: Name of the team (default: DuckPools Development Team)

### Logging
The system uses Python's logging module with INFO level by default.

## Development

### Running Tests
```bash
python -m pytest reports/tests/
```

### Code Structure
```
reports/
├── executive_manager_prompt_template.md  # EM prompt template
├── team_status_reporter.py             # Core reporting logic
├── api_server.py                      # FastAPI service
├── README.md                          # Documentation
└── tests/                             # Test cases
```

## Deployment

### Production Setup
1. Configure environment variables
2. Set up database for persistent storage
3. Deploy the API service
4. Integrate with Paperclip API
5. Set up monitoring and alerts

### Docker Support
The system can be containerized for production deployment.

## Support

For issues or questions, please contact the development team or refer to the Executive Manager prompt template for guidance.