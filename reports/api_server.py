#!/usr/bin/env python3
"""
API Server for Team Status Reporting System

This service provides endpoints for:
1. Task completion notifications
2. Report generation and posting
3. TEAM STATUS REPORT creation
4. CEO notifications
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Team Status Reporting API",
    description="API for implementing the reporting chain system for Executive Managers",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demonstration (would use database in production)
reports_db = {}
tasks_db = {}

class TaskCompletionNotification(BaseModel):
    task_id: str = Field(..., description="ID of the completed task")
    issue_id: str = Field(..., description="ID of the parent issue")
    run_output: str = Field(..., description="Output from the task run")
    metrics: Dict = Field(default_factory=dict, description="Task metrics and results")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    status: str = Field(..., description="Task status: completed/failed/in_progress")

class ReportGenerationRequest(BaseModel):
    issue_id: str = Field(..., description="ID of the parent issue")
    task_results: List[TaskCompletionNotification] = Field(..., description="List of completed tasks")

class ReportResponse(BaseModel):
    report_id: str = Field(..., description="ID of the generated report")
    issue_id: str = Field(..., description="ID of the created TEAM STATUS REPORT issue")
    parent_issue_id: str = Field(..., description="ID of the parent issue")
    status: str = Field(..., description="Status of the reporting process")
    message: str = Field(..., description="Status message")

@app.post("/api/reports/generate", response_model=ReportResponse)
async def generate_report(request: ReportGenerationRequest):
    """Generate and post a team status report when all sub-tasks are complete"""
    logger.info(f"Generating report for issue {request.issue_id}")
    
    try:
        # Store task results
        for task in request.task_results:
            tasks_db[task.task_id] = task.dict()
        
        # Check if all tasks are completed
        all_completed = all(task.status == "completed" for task in request.task_results)
        
        if not all_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not all tasks are completed. Waiting for remaining tasks."
            )
        
        # Generate report
        report_id = f"TSR-{int(time.time())}"
        issue_id = f"MAT-{int(time.time())}"
        
        # Create report data
        report_data = {
            "report_id": report_id,
            "issue_id": issue_id,
            "parent_issue_id": request.issue_id,
            "team_name": "DuckPools Development Team",
            "cycle_start": datetime.now().isoformat(),
            "cycle_end": datetime.now().isoformat(),
            "status": "generated",
            "message": "Report generated successfully"
        }
        
        # Store report
        reports_db[report_id] = report_data
        
        # In production, this would:
        # 1. Call the TeamStatusReporter to compile the report
        # 2. Post the report as a comment on the parent issue
        # 3. Create a TEAM STATUS REPORT issue for the CEO
        # 4. Notify the CEO
        
        logger.info(f"Report generated successfully: {report_id}")
        
        return ReportResponse(
            report_id=report_id,
            issue_id=issue_id,
            parent_issue_id=request.issue_id,
            status="success",
            message="Report generated and TEAM STATUS REPORT issue created"
        )
        
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}"
        )

@app.post("/api/tasks/complete")
async def notify_task_completion(notification: TaskCompletionNotification):
    """Notify when a task is completed"""
    logger.info(f"Task completion notification received: {notification.task_id}")
    
    try:
        # Store task completion
        tasks_db[notification.task_id] = notification.dict()
        
        # Check if all tasks for this issue are completed
        issue_tasks = [t for t in tasks_db.values() if t.get("issue_id") == notification.issue_id]
        all_completed = all(t.get("status") == "completed" for t in issue_tasks)
        
        if all_completed:
            logger.info(f"All tasks completed for issue {notification.issue_id}")
            # Trigger report generation
            report_request = ReportGenerationRequest(
                issue_id=notification.issue_id,
                task_results=[TaskCompletionNotification(**t) for t in issue_tasks]
            )
            # In production, this would call the generate_report endpoint
            # For now, just log it
            logger.info("Would trigger report generation for completed issue")
        
        return {"status": "success", "message": "Task completion recorded"}
        
    except Exception as e:
        logger.error(f"Task notification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task notification failed: {str(e)}"
        )

@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    """Get a specific report by ID"""
    if report_id not in reports_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    return reports_db[report_id]

@app.get("/api/reports")
async def list_reports():
    """List all reports"""
    return list(reports_db.values())

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)