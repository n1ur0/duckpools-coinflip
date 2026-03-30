#!/usr/bin/env python3
"""
Test suite for the Team Status Reporting System
"""

import os
import sys
import unittest
from team_status_reporter import TeamStatusReporter, TaskResult, TeamStatusReport

class TestTeamStatusReporter(unittest.TestCase):
    def setUp(self):
        self.reporter = TeamStatusReporter()
        self.parent_issue_id = "test_issue_123"
    
    def test_task_result_creation(self):
        """Test TaskResult dataclass creation"""
        task = TaskResult(
            task_id="test_task_1",
            task_name="Test Task",
            status="completed",
            output="Task completed successfully",
            metrics={"status": "success"},
            errors=[],
            completed_at=None
        )
        
        self.assertEqual(task.task_id, "test_task_1")
        self.assertEqual(task.task_name, "Test Task")
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.output, "Task completed successfully")
        self.assertEqual(task.metrics, {"status": "success"})
        self.assertEqual(task.errors, [])
    
    def test_team_status_report_creation(self):
        """Test TeamStatusReport dataclass creation"""
        task_results = [
            TaskResult(
                task_id="test_task_1",
                task_name="Test Task 1",
                status="completed",
                output="Task 1 completed",
                metrics={"result": "success"},
                errors=[],
                completed_at=None
            )
        ]
        
        report = self.reporter.compile_summary_report(task_results, self.parent_issue_id)
        
        self.assertIsNotNone(report.report_id)
        self.assertIsNotNone(report.issue_id)
        self.assertEqual(report.parent_issue_id, self.parent_issue_id)
        self.assertEqual(report.team_name, "DuckPools Development Team")
        self.assertIn("Test Task 1", report.executive_summary)
    
    def test_report_formatting(self):
        """Test report formatting for comments"""
        task_results = [
            TaskResult(
                task_id="test_task_1",
                task_name="Security Audit",
                status="completed",
                output="Security audit completed",
                metrics={"vulnerabilities": 2},
                errors=[],
                completed_at=None
            )
        ]
        
        report = self.reporter.compile_summary_report(task_results, self.parent_issue_id)
        comment = self.reporter.format_report_for_comment(report)
        
        self.assertIn("# Task Completion Summary Report", comment)
        self.assertIn("Security Audit", comment)
        self.assertIn("completed", comment)
    
    def test_ceo_report_formatting(self):
        """Test CEO report formatting"""
        task_results = [
            TaskResult(
                task_id="test_task_1",
                task_name="Test Task",
                status="completed",
                output="Test output",
                metrics={"result": "success"},
                errors=[],
                completed_at=None
            )
        ]
        
        report = self.reporter.compile_summary_report(task_results, self.parent_issue_id)
        ceo_report = self.reporter.format_report_for_ceo(report)
        
        self.assertIn("# TEAM STATUS REPORT", ceo_report)
        self.assertIn("Executive Summary", ceo_report)
        self.assertIn("Test Task", ceo_report)

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.api_url = "http://localhost:8001"
    
    def test_health_check(self):
        """Test health check endpoint"""
        try:
            response = requests.get(f"{self.api_url}/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
        except Exception as e:
            self.fail(f"Health check failed: {e}")

def run_tests():
    """Run all tests"""
    print("Running Team Status Reporting System tests...")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

if __name__ == "__main__":
    run_tests()