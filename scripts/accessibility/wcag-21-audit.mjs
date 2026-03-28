#!/usr/bin/env node

/**
 * WCAG 2.1 Accessibility Audit Script
 * 
 * This script runs accessibility checks against all UI components
 * in the DuckPools frontend to ensure WCAG 2.1 compliance.
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Get current directory
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.join(__dirname, '..');

// Use the main DuckPools repository path for components
const mainRepoPath = '/Users/n1ur0/projects/DuckPools';

// Component paths to audit
const componentPaths = [
  path.join(mainRepoPath, 'frontend/src/components/ui'),
  path.join(mainRepoPath, 'frontend/src/components/games'),
  path.join(mainRepoPath, 'frontend/src/components'),
];

// WCAG 2.1 Success Criteria to check
const wcag21Criteria = {
  '1.1.1': 'Non-text Content',
  '1.2.1': 'Audio-only and Video-only (Prerecorded)',
  '1.2.2': 'Captions (Prerecorded)',
  '1.2.3': 'Audio Description or Media Alternative (Prerecorded)',
  '1.2.4': 'Captions (Live)',
  '1.2.5': 'Audio Description (Prerecorded)',
  '1.3.1': 'Info and Relationships',
  '1.3.2': 'Meaningful Sequence',
  '1.3.3': 'Sensory Characteristics',
  '1.3.4': 'Orientation',
  '1.3.5': 'Identify Input Purpose',
  '1.3.6': 'Identify Purpose',
  '1.4.1': 'Use of Color',
  '1.4.2': 'Audio Control',
  '1.4.3': 'Contrast (Minimum)',
  '1.4.4': 'Resize Text',
  '1.4.5': 'Text Spacing',
  '1.4.10': 'Reflow',
  '1.4.11': 'Non-text Contrast',
  '1.4.12': 'Text Spacing',
  '1.4.13': 'Content on Hover or Focus',
  '2.1.1': 'Keyboard',
  '2.1.2': 'No Keyboard Trap',
  '2.1.4': 'Character Key Shortcuts',
  '2.2.1': 'Timing Adjustable',
  '2.2.2': 'Pause, Stop, Hide',
  '2.3.1': 'Three Flashes or Below Threshold',
  '2.4.1': 'Bypass Blocks',
  '2.4.2': 'Page Titled',
  '2.4.3': 'Focus Order',
  '2.4.4': 'Link Purpose (In Context)',
  '2.4.5': 'Multiple Ways',
  '2.4.6': 'Headings and Labels',
  '2.4.7': 'Focus Visible',
  '2.5.1': 'Pointer Gestures',
  '2.5.2': 'Pointer Cancellation',
  '2.5.3': 'Label in Name',
  '2.5.4': 'Motion Actuation',
  '2.5.5': 'Target Size',
  '3.1.1': 'Language of Page',
  '3.1.2': 'Language of Parts',
  '3.2.1': 'On Focus',
  '3.2.2': 'On Input',
  '3.2.3': 'Consistent Navigation',
  '3.2.4': 'Consistent Identification',
  '3.3.1': 'Error Identification',
  '3.3.2': 'Labels or Instructions',
  '3.3.3': 'Error Suggestion',
  '3.3.4': 'Error Prevention (Legal, Financial, Data)',
  '4.1.1': 'Parsing',
  '4.1.2': 'Name, Role, Value',
  '4.1.3': 'Status Messages',
};

// Common accessibility issues to check
const accessibilityChecks = {
  imagesWithoutAlt: [],
  formLabelsMissing: [],
  missingAriaAttributes: [],
  lowContrast: [],
  keyboardNavigation: [],
  headingStructure: [],
  colorOnlyIndicators: [],
  focusManagement: [],
  missingLangAttribute: [],
  missingButtonLabels: [],
  improperAriaRoles: [],
  insufficientColorContrast: [],
};

// Function to get all component files
function getComponentFiles() {
  const componentFiles = [];
  
  for (const componentPath of componentPaths) {
    console.log(`Checking path: ${componentPath}`);
    if (fs.existsSync(componentPath)) {
      console.log(`Path exists: ${componentPath}`);
      const files = getAllFiles(componentPath, ['.tsx', '.jsx']);
      console.log(`Found ${files.length} files in ${componentPath}`);
      componentFiles.push(...files);
    } else {
      console.log(`Path does not exist: ${componentPath}`);
    }
  }
  
  return componentFiles;
}

// Function to recursively get all files
function getAllFiles(dirPath, extensions) {
  const files = [];
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    
    if (entry.isDirectory()) {
      files.push(...getAllFiles(fullPath, extensions));
    } else if (extensions.some(ext => entry.name.endsWith(ext))) {
      files.push(fullPath);
    }
  }
  
  return files;
}

// Function to analyze a component file for accessibility issues
function analyzeComponent(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const issues = [];
  const fileName = path.basename(filePath);
  
  // Check for images without alt text
  const imgTags = content.match(/<img[^>]*>/g) || [];
  imgTags.forEach(img => {
    if (!img.includes('alt=') || img.includes('alt=\"\"') || img.includes('alt=\'\'')) {
      issues.push({
        type: 'imagesWithoutAlt',
        element: img,
        severity: 'high',
        description: 'Image missing alt attribute or has empty alt text',
        suggestion: 'Add descriptive alt text for screen readers'
      });
    }
  });
  
  // Check for form inputs without labels
  const inputTags = content.match(/<input[^>]*>/g) || [];
  inputTags.forEach(input => {
    // More sophisticated check for labels
    const inputId = input.match(/id=\"([^\"]+)\"/);
    const hasLabel = inputId && content.includes(`htmlFor=\"${inputId[1]}\"`) || 
                   inputId && content.includes(` htmlFor=\"${inputId[1]}\"`) ||
                   input.includes('aria-labelledby=') || 
                   input.includes('aria-label=') ||
                   input.includes('title=');
    
    if (!hasLabel) {
      issues.push({
        type: 'formLabelsMissing',
        element: input,
        severity: 'high',
        description: 'Form input missing associated label',
        suggestion: 'Add a label element with htmlFor attribute or use aria-label/aria-labelledby'
      });
    }
  });
  
  // Check for buttons without accessible labels
  const buttonTags = content.match(/<button[^>]*>([^<]*)<\/button>/g) || [];
  buttonTags.forEach(button => {
    const buttonContent = button.match(/<button[^>]*>([^<]*)<\/button>/)[1];
    const hasIconOnly = buttonContent.trim() === '' && 
                       (button.includes('className=') && 
                       (button.includes('icon') || button.includes('Icon')));
    
    if (hasIconOnly && !button.includes('aria-label=')) {
      issues.push({
        type: 'missingButtonLabels',
        element: button,
        severity: 'high',
        description: 'Button with icon only missing aria-label',
        suggestion: 'Add aria-label attribute to describe button functionality for screen readers'
      });
    }
  });
  
  // Check for color-only indicators
  const colorKeywords = ['color:', 'backgroundColor:', 'borderColor:'];
  colorKeywords.forEach(keyword => {
    if (content.includes(keyword)) {
      // Check if color is used with other indicators
      const hasOtherIndicators = content.includes('aria-label') || 
                                content.includes('title=') ||
                                content.includes('alt=');
      
      if (!hasOtherIndicators) {
        issues.push({
          type: 'colorOnlyIndicators',
          element: 'CSS color property',
          severity: 'medium',
          description: 'Potential color-only indicator found',
          suggestion: 'Ensure color is not the only means of conveying information'
        });
      }
    }
  });
  
  // Check for missing ARIA attributes
  if (content.includes('role=') && !content.includes('aria-')) {
    issues.push({
      type: 'missingAriaAttributes',
      element: 'Element with role but missing aria attributes',
      severity: 'medium',
      description: 'Element has role but may be missing required ARIA attributes',
      suggestion: 'Check if required ARIA attributes are present for the role'
    });
  }
  
  // Check for improper ARIA roles
  const improperRoles = ['role="button"', 'role="link"', 'role="img"'];
  improperRoles.forEach(role => {
    if (content.includes(role)) {
      // Check if using semantic HTML instead
      const hasSemanticEquivalent = content.includes('<button') || content.includes('<a href') || content.includes('<img');
      
      if (hasSemanticEquivalent) {
        issues.push({
          type: 'improperAriaRoles',
          element: role,
          severity: 'medium',
          description: 'Using ARIA role when semantic HTML element would be better',
          suggestion: 'Use semantic HTML elements (button, a, img) instead of adding ARIA roles'
        });
      }
    }
  });
  
  // Check for heading structure issues
  const headingTags = content.match(/<h[1-6][^>]*>/g) || [];
  if (headingTags.length > 0) {
    // Check if h1 is used more than once (generally should be only one h1 per page)
    const h1Tags = headingTags.filter(tag => tag.includes('<h1'));
    if (h1Tags.length > 1) {
      issues.push({
        type: 'headingStructure',
        element: `Found ${h1Tags.length} h1 tags`,
        severity: 'medium',
        description: 'Multiple h1 tags found in component',
        suggestion: 'Consider using only one h1 tag per page and using h2-h6 for subsequent headings'
      });
    }
    
    // Check for skipped heading levels
    const headingLevels = headingTags.map(tag => parseInt(tag.match(/<h([1-6])/)[1]));
    for (let i = 1; i < headingLevels.length; i++) {
      if (headingLevels[i] - headingLevels[i-1] > 1) {
        issues.push({
          type: 'headingStructure',
          element: `Skipped heading level from h${headingLevels[i-1]} to h${headingLevels[i]}`,
          severity: 'medium',
          description: 'Skipped heading level detected',
          suggestion: 'Maintain proper heading hierarchy without skipping levels'
        });
        break;
      }
    }
  }
  
  // Check for missing lang attribute (for root components)
  if (fileName.toLowerCase().includes('app') || fileName.toLowerCase().includes('index')) {
    if (!content.includes('lang=')) {
      issues.push({
        type: 'missingLangAttribute',
        element: 'Root component',
        severity: 'high',
        description: 'Missing lang attribute on root element',
        suggestion: 'Add lang attribute to specify the language of the page content'
      });
    }
  }
  
  // Check for focus management issues
  if (content.includes('focus') || content.includes('Focus')) {
    // Check if focus is properly managed
    const hasFocusTrap = content.includes('trapFocus') || content.includes('FocusTrap');
    const hasFocusManagement = content.includes('useRef') && content.includes('focus');
    
    if (hasFocusTrap && !hasFocusManagement) {
      issues.push({
        type: 'focusManagement',
        element: 'Focus trap without proper management',
        severity: 'medium',
        description: 'Focus trap detected but focus management may be incomplete',
        suggestion: 'Ensure proper focus management when trapping focus (e.g., restore focus on close)'
      });
    }
  }
  
  return issues;
}

// Function to generate HTML report
function generateHtmlReport(issues) {
  const reportPath = path.join(projectRoot, 'accessibility-report.html');
  
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WCAG 2.1 Accessibility Audit Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5rem;
        }
        .summary {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }
        .stat-value {
            font-size: 2rem;
            font-weight: bold;
            color: #2c3e50;
        }
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        .issues {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .issue-item {
            border-left: 4px solid #e74c3c;
            padding: 15px;
            margin-bottom: 15px;
            background: #fdf2f2;
            border-radius: 0 4px 4px 0;
        }
        .issue-item.medium {
            border-left-color: #f39c12;
            background: #fef9f2;
        }
        .issue-item.low {
            border-left-color: #3498db;
            background: #f2f8fd;
        }
        .issue-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .issue-type {
            font-weight: bold;
            color: #2c3e50;
        }
        .severity-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        .severity-high {
            background: #e74c3c;
            color: white;
        }
        .severity-medium {
            background: #f39c12;
            color: white;
        }
        .severity-low {
            background: #3498db;
            color: white;
        }
        .issue-description {
            margin-bottom: 10px;
        }
        .issue-suggestion {
            font-style: italic;
            color: #666;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        .wcag-section {
            margin-top: 30px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .wcag-section h2 {
            color: #2c3e50;
            margin-bottom: 15px;
        }
        .wcag-criteria {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 10px;
        }
        .wcag-item {
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 3px solid #3498db;
        }
        .wcag-item h4 {
            margin: 0 0 5px 0;
            color: #2c3e50;
        }
        .wcag-item p {
            margin: 0;
            font-size: 0.9rem;
            color: #666;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #666;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>WCAG 2.1 Accessibility Audit Report</h1>
        <p>Generated on ${new Date().toISOString()}</p>
        <p>DuckPools Frontend Components</p>
    </div>
    
    <div class="summary">
        <h2>Executive Summary</h2>
        <p>This report details the accessibility audit findings for all UI components in the DuckPools frontend application, checked against WCAG 2.1 guidelines.</p>
        
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-value">${issues.length}</div>
                <div class="stat-label">Total Issues Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${issues.filter(i => i.severity === 'high').length}</div>
                <div class="stat-label">High Priority</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${issues.filter(i => i.severity === 'medium').length}</div>
                <div class="stat-label">Medium Priority</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${issues.filter(i => i.severity === 'low').length}</div>
                <div class="stat-label">Low Priority</div>
            </div>
        </div>
    </div>
    
    <div class="issues">
        <h2>Detailed Issues</h2>
        ${issues.length === 0 ? 
            '<p>No accessibility issues found! Great job on accessibility compliance.</p>' :
            issues.map(issue => `
                <div class="issue-item ${issue.severity}">
                    <div class="issue-header">
                        <span class="issue-type">${issue.type}</span>
                        <span class="severity-badge severity-${issue.severity}">${issue.severity}</span>
                    </div>
                    <div class="issue-description">${issue.description}</div>
                    <div class="issue-suggestion">💡 ${issue.suggestion}</div>
                </div>
            `).join('')
        }
    </div>
    
    <div class="wcag-section">
        <h2>WCAG 2.1 Success Criteria</h2>
        <p>The audit was performed against the following WCAG 2.1 success criteria:</p>
        <div class="wcag-criteria">
            ${Object.entries(wcag21Criteria).map(([code, title]) => `
                <div class="wcag-item">
                    <h4>${code}</h4>
                    <p>${title}</p>
                </div>
            `).join('')}
        </div>
    </div>
    
    <div class="footer">
        <p>This report was generated automatically by the WCAG 2.1 Accessibility Audit Script.</p>
        <p>For questions about accessibility implementation, please contact the development team.</p>
    </div>
</body>
</html>
  `;
  
  fs.writeFileSync(reportPath, html);
  return reportPath;
}

// Main function
function main() {
  console.log('🔍 Starting WCAG 2.1 Accessibility Audit...');
  console.log('==========================================');
  
  // Get all component files
  const componentFiles = getComponentFiles();
  console.log(`📁 Found ${componentFiles.length} component files to audit`);
  
  // Analyze each component
  const allIssues = [];
  for (const filePath of componentFiles) {
    console.log(`🔍 Analyzing ${filePath}`);
    const issues = analyzeComponent(filePath);
    allIssues.push(...issues);
    
    if (issues.length > 0) {
      console.log(`  ⚠️  Found ${issues.length} issues in ${path.basename(filePath)}`);
    } else {
      console.log(`  ✅ No issues found in ${path.basename(filePath)}`);
    }
  }
  
  // Group issues by type
  const issuesByType = {};
  allIssues.forEach(issue => {
    if (!issuesByType[issue.type]) {
      issuesByType[issue.type] = [];
    }
    issuesByType[issue.type].push(issue);
  });
  
  // Print summary
  console.log('\n📊 Audit Summary');
  console.log('===============');
  console.log(`Total issues found: ${allIssues.length}`);
  console.log(`High priority: ${allIssues.filter(i => i.severity === 'high').length}`);
  console.log(`Medium priority: ${allIssues.filter(i => i.severity === 'medium').length}`);
  console.log(`Low priority: ${allIssues.filter(i => i.severity === 'low').length}`);
  
  if (allIssues.length > 0) {
    console.log('\n⚠️  Issues by type:');
    Object.entries(issuesByType).forEach(([type, issues]) => {
      console.log(`  ${type}: ${issues.length} issues`);
    });
  }
  
  // Generate HTML report
  console.log('\n📄 Generating HTML report...');
  const reportPath = generateHtmlReport(allIssues);
  console.log(`✅ Report generated: ${reportPath}`);
  
  // Create JSON report for programmatic use
  const jsonReportPath = path.join(projectRoot, 'accessibility-report.json');
  fs.writeFileSync(jsonReportPath, JSON.stringify({
    timestamp: new Date().toISOString(),
    totalIssues: allIssues.length,
    issuesByType: issuesByType,
    issues: allIssues,
    wcag21Criteria: wcag21Criteria
  }, null, 2));
  console.log(`✅ JSON report generated: ${jsonReportPath}`);
  
  console.log('\n🎉 Accessibility audit complete!');
  console.log('==============================');
  console.log('Next steps:');
  console.log('1. Review the HTML report for detailed findings');
  console.log('2. Address high-priority issues first');
  console.log('3. Re-run the audit after fixes to verify improvements');
  console.log('4. Consider integrating this script into your CI/CD pipeline');
  
  if (allIssues.length > 0) {
    console.log('\n⚠️  Important: Accessibility is critical for inclusive design.');
    console.log('   Please address the identified issues to ensure your application');
    console.log('   is accessible to all users, including those with disabilities.');
  }
}

// Run the audit
try {
  main();
} catch (error) {
  console.error('❌ Error running accessibility audit:', error);
  process.exit(1);
}