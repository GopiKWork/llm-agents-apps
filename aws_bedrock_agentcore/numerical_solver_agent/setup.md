# Numerical Solver Agent with Private MCP Server Setup Guide

This guide walks you through deploying a Bedrock AgentCore Numerical Solver Agent in a VPC that connects to a private MATLAB MCP server running on EC2.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Setup Flow](#setup-flow)
- [Detailed Instructions](#detailed-instructions)
- [Testing](#testing)
- [Cleanup](#cleanup)

---
## Prerequisites

- Python 3.11+
- `uv` package manager installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- AWS CLI configured with appropriate credentials
- AWS account with:
  - VPC with private subnet
  - EC2 instance in private subnet
  - Security group allowing port 8000
  - S3 bucket for file transfer
  - Permissions for Bedrock AgentCore and IAM

---

## Setup Flow

The setup process follows these stages:

1. **Local Environment Setup** - Install dependencies on your local machine
2. **EC2 MCP Server Setup** - Deploy MCP server to EC2 via S3
3. **Configuration** - Update settings with VPC and MCP server details
4. **Agent Deployment** - Deploy agent to Bedrock AgentCore with VPC config
5. **Testing** - Invoke agent and test MATLAB tools

---

## Detailed Instructions

### 1. Local Environment Setup

Create and activate a Python virtual environment using `uv`:

```bash
cd numerical_solver_agent

# Create virtual environment
uv venv

# Activate the environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

**What's installed:**
- AWS SDK (boto3)
- Bedrock AgentCore toolkit
- Strands agent framework
- MCP client libraries
- Jinja2 for templating

---

### 2. EC2 MCP Server Setup

#### Step 2.1: Upload Files to S3

From your local machine, copy the matlab folder contents to S3:

```bash
# Navigate to project root
cd ..

# Create S3 bucket (if needed)
aws s3 mb s3://your-bucket-name

# Upload matlab folder
aws s3 cp matlab/ s3://your-bucket-name/matlab/ --recursive
```

#### Step 2.2: Connect to EC2 Instance

SSH into your EC2 instance that's in the private subnet:

```bash
# Use bastion host or Systems Manager Session Manager
aws ssm start-session --target i-xxxxxxxxxxxxxxxxx

# Or via SSH if you have bastion
ssh -i your-key.pem ec2-user@bastion-ip
ssh ec2-user@private-ec2-ip
```

#### Step 2.3: Download Files from S3

On the EC2 instance:

```bash
# Download files from S3
aws s3 cp s3://your-bucket-name/matlab/ ~/matlab/ --recursive

cd ~/matlab
```

#### Step 2.4: Install UV on EC2

If `uv` is not installed, download it:

```bash
# Download and install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.bashrc for persistence)
export PATH="$HOME/.cargo/bin:$PATH"

# Verify installation
uv --version
```

#### Step 2.5: Setup Python Environment on EC2

```bash
# Create virtual environment
uv venv

# Activate environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

#### Step 2.6: Launch MCP Server

```bash
# Start the MATLAB MCP server
uv run matlab_mcp.py
```

**Important:** The `matlab_mcp.py` script is a test implementation that provides MATLAB-style mathematical functions. It is not the full MATLAB software and includes only a limited set of computational tools (15 functions) for demonstration purposes.

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Note the private IP address** of your EC2 instance:
```bash
# Get private IP
curl http://169.254.169.254/latest/meta-data/local-ipv4
```

Example: `10.0.1.100`

**MCP Server URL:** `http://10.0.1.100:8000/mcp`

Keep the server running. You can use `screen` or `tmux` to keep it alive:
```bash
# Using screen
screen -S mcp
uv run matlab_mcp.py
# Press Ctrl+A then D to detach

# To reattach later
screen -r mcp
```

---

### 3. Configuration

Back on your local machine, update the settings file with your VPC and MCP server details.

Edit `numerical_solver_agent/settings.json`:

```json
{
  "vpc": {
    "vpc_id": "vpc-xxxxxxxxxx",
    "subnet_id": "subnet-xxxxxxxxxx",
    "security_group_id": "sg-xxxxxxxxxx"
  },
  "matlab_mcp": {
    "url": "http://10.0.1.100:8000/mcp"
  },
  "agent": {
    "name": "numerical-solver-agent",
    "arn": "",
    "model_id": "global.anthropic.claude-haiku-4-5-20251001-v1:0"
  },
  "aws": {
    "region": "us-west-2"
  }
}
```

**Replace with your values:**
- `vpc_id`: Your VPC ID
- `subnet_id`: Private subnet ID where EC2 is running
- `security_group_id`: Security group that allows outbound to port 8000
- `url`: Private IP of EC2 instance with `/mcp` path
- `region`: Your AWS region

**Security Group Requirements:**
- Outbound: Allow TCP port 8000 to EC2 private IP
- EC2 Security Group: Allow inbound TCP port 8000 from agent's security group

---

### 4. Agent Deployment

Deploy the numerical solver agent to Bedrock AgentCore with VPC configuration:

```bash
cd numerical_solver_agent
uv run setup_agent.py
```

**What happens:**
1. Loads settings from `settings.json`
2. Renders agent runtime code from Jinja2 template with MCP URL
3. Creates Docker container with dependencies
4. Deploys to Bedrock AgentCore with VPC settings
5. Waits for deployment to complete (2-5 minutes)
6. Saves agent ARN to `settings.json`

**Expected output:**
```
============================================================
SETUP BEDROCK AGENTCORE WITH VPC CONFIGURATION
============================================================

Loading settings...
   VPC ID:           vpc-xxxxxxxxxx
   Subnet ID:        subnet-xxxxxxxxxx
   Security Group:   sg-xxxxxxxxxx
   MATLAB MCP URL:   http://10.0.1.100:8000/mcp
   Agent Name:       numerical-solver-agent

Preparing runtime code...
Runtime code prepared: .../agent.py

AWS Region: us-west-2

Initializing AgentCore Runtime with VPC...

Configuring runtime...
   Runtime configured with VPC settings

Launching runtime...
   Runtime launched

Waiting for deployment...
   Status: CREATING
   Status: CREATING
   ...
   Status: READY

Final status: READY

============================================================
DEPLOYMENT SUCCESSFUL
============================================================

Agent ARN: arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/numerical-solver-agent-XXXXXXXXXX

Agent is deployed in VPC with:
  - Subnet: subnet-xxxxxxxxxx
  - Security Group: sg-xxxxxxxxxx
  - MATLAB MCP: http://10.0.1.100:8000/mcp

Authentication: IAM (no Cognito)
```

---

## Testing

### 1. Single Invocation Mode

Test the agent with a single prompt:

```bash
uv run invoke_agent.py "Calculate the mean of 10, 20, 30, 40, 50"
```

**Expected output:**
```
Agent: The mean of the numbers 10, 20, 30, 40, and 50 is 30.0
```

### 2. Interactive Mode with Sample Prompts

Run the agent in interactive mode with pre-defined sample prompts:

```bash
uv run invoke_agent.py
```

**Expected output:**
```
============================================================
NUMERICAL SOLVER AGENT - INTERACTIVE MODE
============================================================

Sample prompts (enter number to use, or type your own):

 1. Calculate the mean and standard deviation of [15, 23, 18, 42, 31, 28, 19]
 2. Solve the quadratic equation 2x^2 + 5x - 3 = 0
 3. Generate 10 evenly spaced numbers between 0 and 100
 4. Convert 75 degrees Fahrenheit to Celsius
 5. Calculate the mean of [68, 72, 75, 70, 73] in Fahrenheit, then convert to Celsius
 6. Generate 5 numbers from 1 to 9, use first three as coefficients for quadratic equation
 7. Find max and min in [12, 18, 24, 30, 36], then calculate their GCD and LCM
 8. Calculate sin(π/6) and cos(π/6), then find what percentage sine is of cosine
 9. Evaluate polynomial [1, -2, 1] at x=5, then calculate factorial of the result
10. Generate 10 numbers from 0 to 100, find mean and std, convert mean to Celsius, find std as percentage of mean

 0. Enter custom prompt
 q. Quit

============================================================

Connected to: numerical-solver-agent
ARN: arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/numerical-solver-agent-XXXXXXXXXX

============================================================

Select prompt number or enter custom (q to quit): 
```

**Example conversation:**
```
Select prompt number or enter custom (q to quit): 2

Selected: Solve the quadratic equation 2x^2 + 5x - 3 = 0

Agent: Let me solve this quadratic equation for you.

For the equation 2x² + 5x - 3 = 0:
- a = 2
- b = 5  
- c = -3

The discriminant is: 5² - 4(2)(-3) = 25 + 24 = 49

Since the discriminant is positive, we have two real roots:
- Root 1: 0.5
- Root 2: -3.0

Select prompt number or enter custom (q to quit): 4

Selected: Convert 75 degrees Fahrenheit to Celsius

Agent: 75°F is equal to 23.89°C

Select prompt number or enter custom (q to quit): q

Goodbye!
```

### 3. Custom Prompts

You can also enter custom prompts directly:

```
Select prompt number or enter custom (q to quit): What is the square root of 144 plus the factorial of 5?

Agent: Let me calculate that for you:
- Square root of 144 = 12
- Factorial of 5 = 120
- Sum: 12 + 120 = 132
```

### 4. Error Diagnostics

If tools aren't working, ask the agent for error details:

```
Select prompt number or enter custom (q to quit): Show me the error log
```

The agent will use the `get_error_log` tool to display any errors encountered during MCP initialization or tool execution.

---

## Cleanup

When you're done testing, clean up AWS resources.

### Destroy Agent and Clean Up Files

Use the provided cleanup script:

```bash
cd numerical_solver_agent
./cleanup.sh
```

Or run the commands manually:

```bash
# Destroy the agent
uv run agentcore destroy

# Remove generated files
rm -f Dockerfile .dockerignore agent.py .bedrock_agentcore.yaml
```

**What's deleted:**
- Bedrock AgentCore runtime
- ECR repository (if you select yes when prompted)
- IAM execution role
- Generated files (Dockerfile, .dockerignore, agent.py, .bedrock_agentcore.yaml)

**Manual step:**

After cleanup, clear the agent ARN from `settings.json`:
```json
{
  "agent": {
    "name": "numerical-solver-agent",
    "arn": "",
    ...
  }
}
```

### Stop MCP Server on EC2

SSH back to EC2 and stop the MCP server:

```bash
# If using screen
screen -r mcp
# Press Ctrl+C to stop server
# Type 'exit' to close screen session

# Or just kill the process
pkill -f matlab_mcp.py
```

### Clean Up S3 Files (Optional)

If you uploaded files to S3, clean them up:

```bash
# Delete S3 files
aws s3 rm s3://your-bucket-name/matlab/ --recursive
```

---

## File Reference

### Configuration Files

- **`settings.json`**: VPC, MCP server, and agent configuration
- **`requirements.txt`**: Python dependencies
- **`agent.py.template`**: Jinja2 template for agent runtime code
- **`cleanup.sh`**: Cleanup script for destroying agent and removing files

### Python Scripts

- **`setup_agent.py`**: Deploy numerical solver agent with VPC configuration
- **`invoke_agent.py`**: Invoke agent (single or interactive mode with sample prompts)

### Generated Files (Auto-created)

- **`agent.py`**: Rendered agent runtime code
- **`Dockerfile`**: Container definition (auto-generated)
- **`.dockerignore`**: Docker ignore file (auto-generated)

---

## Agent Runtime Features

### Fresh MCP Connection Per Request

The agent creates a new MCP connection for each invocation:
- **No stale connections**: If MCP server restarts, next request works
- **Automatic retry**: Connection failures are logged and retried
- **Error tracking**: All errors logged with timestamps and tracebacks

### Available Tools (22 Total)

**MATLAB MCP Tools (15):**

*Note: These are test implementations simulating MATLAB-style functions, not the full MATLAB software.*

- `linspace` - Generate linearly spaced vectors
- `mean` - Calculate mean of array
- `std` - Calculate standard deviation
- `max_value`, `min_value` - Find extrema
- `sum_array`, `prod` - Array aggregation
- `sqrt_value`, `abs_value` - Basic math
- `sin_value`, `cos_value` - Trigonometry
- `exp_value`, `log_value` - Exponential/logarithm
- `polyval` - Polynomial evaluation
- `diff` - Consecutive differences

**Local Computational Tools (5):**
- `solve_quadratic` - Solve ax²+bx+c=0 (real and complex roots)
- `factorial` - Calculate n! for non-negative integers
- `gcd_lcm` - Greatest Common Divisor and Least Common Multiple
- `convert_units` - Convert length, temperature, weight units
- `percentage_calculator` - Percentage operations

**Utility Tools (2):**
- `get_time` - Returns current timestamp
- `get_error_log` - Returns detailed error log with tracebacks

---

## Sample Problems the Agent Can Solve

1. **Statistical Analysis**: "Calculate mean, standard deviation, and range of [12, 45, 23, 67, 34, 89, 15]"

2. **Equation Solving**: "Solve 3x² - 7x + 2 = 0"

3. **Array Generation**: "Generate 20 evenly spaced numbers between -5 and 5"

4. **Unit Conversion**: "Convert 100 kilometers to miles"

5. **Percentage Problems**: "What is 18% of 450?"

6. **Number Theory**: "Find GCD and LCM of 84 and 126"

7. **Trigonometry**: "Calculate sin(30°) and cos(60°)"

8. **Polynomial Evaluation**: "Evaluate polynomial 2x³ - 5x² + 3x - 1 at x=4"

9. **Factorial**: "What is 10 factorial?"

10. **Temperature Conversion**: "Convert 98.6°F to Celsius and Kelvin"

---

## Troubleshooting

### Agent Can't Connect to MCP Server

**Problem:** Agent reports "client session is not running"

**Solutions:**
1. Verify MCP server is running on EC2: `ps aux | grep matlab_mcp`
2. Check EC2 private IP is correct in `settings.json`
3. Verify security group allows outbound port 8000
4. Test connectivity from agent's subnet to EC2

### Deployment Fails with VPC Error

**Problem:** "VPC configuration invalid"

**Solutions:**
1. Verify subnet is in the same VPC
2. Check security group belongs to the VPC
3. Ensure subnet has route to EC2 instance
4. Verify IAM role has VPC permissions

### Tools Return Empty Results

**Problem:** Agent lists tools but they don't execute

**Solutions:**
1. Check MCP server logs on EC2
2. Ask agent: "Show me the error log"
3. Verify MCP URL ends with `/mcp`
4. Redeploy agent: `uv run setup_vpc_agent.py`

### Agent Cleanup

**Problem:** Need to destroy the agent and clean up files

**Solution:** Use the cleanup script:
```bash
cd numerical_solver_agent
./cleanup.sh
```

Or manually:
```bash
uv run agentcore destroy
rm -f Dockerfile .dockerignore agent.py .bedrock_agentcore.yaml
```

Then clear the ARN in `settings.json`

### MCP Server Won't Start on EC2

**Problem:** Port 8000 already in use

**Solutions:**
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
uv run matlab_mcp.py --port 8001
# Update settings.json with new port
```

---

## Key Configuration Details

### VPC Requirements

- **Subnet Type**: Private subnet (no internet gateway)
- **Route Table**: Must route to EC2 instance's subnet
- **Security Group**: Outbound TCP 8000 to EC2
- **EC2 Security Group**: Inbound TCP 8000 from agent's security group

### Agent Runtime Configuration

```python
# Agent initialized per request
def create_agent():
    # Fresh MCP connection
    mcp_client = initialize_mcp_client()
    
    # Load tools
    mcp_tools = get_mcp_tools(mcp_client)
    
    # Create agent with tools
    agent = Agent(model=model, tools=mcp_tools + custom_tools)
    
    return agent, mcp_client

# Cleanup after each request
finally:
    if mcp_client:
        mcp_client.__exit__(None, None, None)
```

### Settings File Structure

```json
{
  "vpc": {
    "vpc_id": "vpc-xxxxxxxxxx",
    "subnet_id": "subnet-xxxxxxxxxx",
    "security_group_id": "sg-xxxxxxxxxx"
  },
  "matlab_mcp": {
    "url": "http://10.0.1.100:8000/mcp"
  },
  "agent": {
    "name": "numerical-solver-agent",
    "arn": "Auto-populated after deployment",
    "model_id": "Bedrock model ID"
  },
  "aws": {
    "region": "AWS region"
  }
}
```

---

## Additional Resources

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Strands Agent Framework](https://strandsagents.com/)
- [UV Package Manager](https://docs.astral.sh/uv/)

---

## Next Steps

- Add custom tools to `vpc_agent_runtime.py.template`
- Implement multi-agent workflows
- Add CloudWatch logging and monitoring
- Scale MCP server with Auto Scaling Group
- Implement health checks and automatic recovery

