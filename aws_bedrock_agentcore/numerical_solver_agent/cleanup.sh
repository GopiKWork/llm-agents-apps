#!/bin/bash
# Cleanup script for numerical solver agent

echo "============================================================"
echo "CLEANUP NUMERICAL SOLVER AGENT"
echo "============================================================"
echo ""

# Destroy agent using agentcore CLI
echo "Destroying agent..."
uv run agentcore destroy

# Check if destroy was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "Agent destroyed successfully"
    echo ""
    
    # Remove generated files
    echo "Cleaning up generated files..."
    
    if [ -f "Dockerfile" ]; then
        rm -f Dockerfile
        echo "  Removed: Dockerfile"
    fi
    
    if [ -f ".dockerignore" ]; then
        rm -f .dockerignore
        echo "  Removed: .dockerignore"
    fi
    
    if [ -f "agent.py" ]; then
        rm -f agent.py
        echo "  Removed: agent.py"
    fi
    
    if [ -f ".bedrock_agentcore.yaml" ]; then
        rm -f .bedrock_agentcore.yaml
        echo "  Removed: .bedrock_agentcore.yaml"
    fi
    
    echo ""
    echo "============================================================"
    echo "CLEANUP COMPLETE"
    echo "============================================================"
    echo ""
    echo "Note: Please manually clear the agent ARN in settings.json"
    
else
    echo ""
    echo "Agent destroy failed. Please check the error above."
    exit 1
fi
