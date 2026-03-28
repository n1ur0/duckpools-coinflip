# WCAG 2.1 Accessibility Audit Script

This script runs automated accessibility checks against all UI components in the DuckPools frontend to ensure WCAG 2.1 compliance.

## Features

- Comprehensive WCAG 2.1 compliance checking
- Automated analysis of React/TSX/JSX components
- Detailed HTML and JSON reports
- Integration with CI/CD pipelines
- Extensible for custom accessibility rules

## Accessibility Checks Performed

### High Priority Issues
1. **Images Without Alt Text**: Detects `<img>` tags missing `alt` attributes
2. **Form Labels Missing**: Identifies form inputs without associated labels
3. **Button Labels Missing**: Finds buttons (especially icon-only) without `aria-label`
4. **Missing Lang Attribute**: Checks for missing `lang` attribute on root components

### Medium Priority Issues
1. **Color-Only Indicators**: Detects when color is the only means of conveying information
2. **Missing ARIA Attributes**: Identifies elements with `role` but missing required ARIA attributes
3. **Improper ARIA Roles**: Finds usage of ARIA roles when semantic HTML would be better
4. **Heading Structure**: Checks for proper heading hierarchy (h1-h6)
5. **Focus Management**: Identifies potential focus management issues in modals and dialogs

## Usage

### Basic Usage
```bash
node scripts/wcag-21-audit.mjs
```

### With Configuration (Coming Soon)
```bash
node scripts/wcag-21-audit.mjs --config accessibility-config.json
```

### CI/CD Integration
Add to your CI/CD pipeline:
```yaml
- name: Run Accessibility Audit
  run: node scripts/wcag-21-audit.mjs
  continue-on-error: true
- name: Upload Accessibility Report
  uses: actions/upload-artifact@v3
  if: always()
  with:
    name: accessibility-report
    path: |
      accessibility-report.html
      accessibility-report.json
```

## Output

The script generates two reports:

1. **HTML Report** (`accessibility-report.html`)
   - Visual, easy-to-read format
   - Color-coded by severity
   - Includes WCAG 2.1 criteria reference
   - Suggestions for fixes

2. **JSON Report** (`accessibility-report.json`)
   - Machine-readable format
   - Programmatic access to all findings
   - Structured data for CI/CD integrations

## WCAG 2.1 Criteria Covered

This script checks against key WCAG 2.1 success criteria:

- **Perceivable**: 1.1.1, 1.3.1, 1.3.3, 1.4.1, 1.4.3
- **Operable**: 2.1.1, 2.4.3, 2.4.7, 2.5.5
- **Understandable**: 3.1.1, 3.2.4, 3.3.2
- **Robust**: 4.1.1, 4.1.2

## Reporting Issues

When issues are found, they are categorized by:

- **Type**: The accessibility violation category
- **Element**: The specific component or code snippet
- **Severity**: High, Medium, or Low
- **Description**: Clear explanation of the issue
- **Suggestion**: Recommended fix

## Example Output

```
🔍 Starting WCAG 2.1 Accessibility Audit...
==========================================
📁 Found 40 component files to audit
🔍 Analyzing /path/to/components/Button.tsx
  ✅ No issues found in Button.tsx
🔍 Analyzing /path/to/components/Input.tsx
  ⚠️  Found 1 issues in Input.tsx

📊 Audit Summary
===============
Total issues found: 15
High priority: 12
Medium priority: 3
Low priority: 0

⚠️  Issues by type:
  formLabelsMissing: 12 issues
  colorOnlyIndicators: 3 issues

📄 Generating HTML report...
✅ Report generated: accessibility-report.html
✅ JSON report generated: accessibility-report.json
```

## Next Steps After Audit

1. **Review the HTML report** for detailed findings
2. **Address high-priority issues first** (especially form labels and image alt text)
3. **Re-run the audit** after fixes to verify improvements
4. **Integrate into CI/CD pipeline** for ongoing accessibility compliance
5. **Consider manual testing** with screen readers for comprehensive validation

## Limitations

This is an automated audit tool and has some limitations:

- Cannot detect all accessibility issues (requires manual testing)
- May produce false positives/negatives
- Does not test actual user experience
- Cannot verify color contrast ratios (requires visual testing)

For complete accessibility compliance, combine this automated audit with:

1. Manual testing with screen readers (NVDA, VoiceOver, JAWS)
2. Keyboard-only navigation testing
3. Color contrast verification
4. User testing with people with disabilities

## Contributing

To extend the script with additional checks:

1. Add new check types to `accessibilityChecks` object
2. Implement the check logic in `analyzeComponent()` function
3. Update the HTML report generation if needed
4. Add documentation for the new check

## License

This script is part of the DuckPools project and follows the same license terms.