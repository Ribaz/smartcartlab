#!/bin/bash
# ==============================================================================
# SmartCartLab - Social Batch Pipeline Launcher
# Handles virtualenv activation, path configuration, execution, and logging.
# ==============================================================================

# Ensure script is executed from the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Ensure logs directory exists
mkdir -p logs

# Activate Python Virtual Environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Virtual environment (venv/.venv) not found." >> logs/social_pipeline.log
    exit 1
fi

# Set PYTHONPATH to project root to resolve modules correctly
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Run the Social Batch Pipeline
echo "==============================================================================" >> logs/social_pipeline.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Social Pipeline Run..." >> logs/social_pipeline.log

python3 main_social_pipeline.py >> logs/social_pipeline.log 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Social Pipeline completed successfully." >> logs/social_pipeline.log
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Social Pipeline exited with status code $EXIT_CODE." >> logs/social_pipeline.log
fi

echo "==============================================================================" >> logs/social_pipeline.log
exit $EXIT_CODE