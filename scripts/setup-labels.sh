#!/bin/bash
LABELS=(
  "priority:high" "ff0000" "Must do this sprint"
  "priority:medium" "ff9900" "Should do this sprint"
  "priority:low" "00ff00" "Nice to have"
  "domain:protocol" "0000ff" "ErgoTree contracts"
  "domain:backend" "8800ff" "FastAPI server"
  "domain:frontend" "0088ff" "React SPA"
  "domain:security" "ff0088" "Audits, pen testing"
  "domain:devops" "888888" "CI/CD, Docker, infra"
  "status:blocked" "000000" "Waiting on dependency"
  "status:needs-review" "ffff00" "PR open, awaiting review"
)
for label in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<< "$label"
  ~/bin/gh label create "$name" --color "$color" --description "$desc" 2>/dev/null || echo "Label $name exists"
done
