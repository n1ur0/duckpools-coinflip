#!/usr/bin/env python3
"""
Demo script for the Team Status Reporting System

This script demonstrates how to use the reporting system to:
1. Monitor task completion
2. Generate reports
3. Post reports as comments
4. Create TEAM STATUS REPORT issues
"""

import os
import sys
import time
import requests
from team_status_reporter import TeamStatusReporter

def demo_reporting_system():
    """Demonstrate the reporting system functionality"""
    print("=== Team Status Reporting System Demo ===\n")
    
    # Initialize reporter
    reporter = TeamStatusReporter()
    
    # Demo parent issue ID (MAT-153)
    parent_issue_id = "5f9d0845-a6e3-4387-8024-ff176dbf30c2"
    
    print(f"1. Monitoring task completion for issue: {parent_issue_id}")
    print("   - Reading run outputs from team members")
    print("   - Checking task status and metrics")
    print()
    
    # Simulate task monitoring
    task_results = reporter.monitor_task_completion(parent_issue_id)
    
    print("2. Task results collected:")
    for i, task in enumerate(task_results, 1):
        print(f"   {i}. {task.task_name}: {task.status.upper()}")
        print(f"      - Output: {task.output}")
        print(f"      - Metrics: {task.metrics}")
        if task.errors:
            print(f"      - Errors: {', '.join(task.errors)}")
        print()
    
    print("3. Compiling summary report...")
    report = reporter.compile_summary_report(task_results, parent_issue_id)
    
    print(f"   Report ID: {report.report_id}")
    print(f"   Issue ID: {report.issue_id}")
    print(f"   Executive Summary: {report.executive_summary}")
    print()
    
    print("4. Posting report as comment on parent issue...")
    reporter.post_report_as_comment(report, parent_issue_id)
    print()
    
    print("5. Creating TEAM STATUS REPORT issue for CEO...")
    issue_id = reporter.create_team_status_report_issue(report)
    print(f"   Created issue: {issue_id}")
    print()
    
    print("6. Notifying CEO to review the report...")
    reporter.notify_ceo(report)
    print()
    
    print("=== Demo Completed Successfully ===")
    print("\nThe reporting system has demonstrated:")
    print("- Task monitoring and output collection")
    print("- Report compilation with metrics and findings")
    print("- Comment posting on parent issues")
    print("- TEAM STATUS REPORT creation for leadership")
    print("- CEO notification workflow")

def demo_api_integration():
    """Demonstrate API integration"""
    print("\n=== API Integration Demo ===\n")
    
    api_url = "http://localhost:8001"
    
    # Test health check
    print("1. Testing health check endpoint...")
    try:
        response = requests.get(f"{api_url}/health")
        print(f"   Status: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test task completion notification
    print("\n2. Testing task completion notification...")
    task_data = {
        "task_id": "demo_task_1",
        "issue_id": "demo_parent_1",
        "run_output": "Demo task completed successfully",
        "metrics": {"status": "success"},
        "errors": [],
        "status": "completed"
    }
    
    try:
        response = requests.post(f"{api_url}/api/tasks/complete", json=task_data)
        print(f"   Status: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test report generation
    print("\n3. Testing report generation...")
    report_data = {
        "issue_id": "demo_parent_1",
        "task_results": [task_data]
    }
    
    try:
        response = requests.post(f"{api_url}/api/reports/generate", json=report_data)
        print(f"   Status: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    try:
        demo_reporting_system()
        demo_api_integration()
    except Exception as e:
        print(f"Demo failed: {e}")
        sys.exit(1)