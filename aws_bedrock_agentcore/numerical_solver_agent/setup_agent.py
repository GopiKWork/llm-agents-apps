#!/usr/bin/env python3
"""
Setup Bedrock AgentCore Runtime with VPC configuration
Deploys agent with IAM authentication in private subnet
"""

from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
import json
import time
from pathlib import Path

def load_settings():
    """Load all settings from settings.json"""
    settings_file = Path(__file__).parent / "settings.json"
    
    if not settings_file.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_file}")
    
    with open(settings_file, 'r') as f:
        return json.load(f)

def save_settings(settings):
    """Save updated settings to settings.json"""
    settings_file = Path(__file__).parent / "settings.json"
    
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    print(f"Settings updated: {settings_file}")

def prepare_runtime_code(matlab_mcp_url):
    """Prepare runtime code with MCP URL using Jinja2 template"""
    from jinja2 import Template
    
    template_file = Path(__file__).parent / "agent.py.template"
    output_file = Path(__file__).parent / "agent.py"
    
    # Read template
    with open(template_file, 'r') as f:
        template_content = f.read()
    
    # Render template with Jinja2
    template = Template(template_content)
    rendered_code = template.render(matlab_mcp_url=matlab_mcp_url)
    
    # Write deployment version
    with open(output_file, 'w') as f:
        f.write(rendered_code)
    
    print(f"Runtime code prepared: {output_file}")
    return output_file

def main():
    print("="*60)
    print("SETUP BEDROCK AGENTCORE WITH VPC CONFIGURATION")
    print("="*60)
    
    # Load settings
    print("\nLoading settings...")
    settings = load_settings()
    
    vpc_id = settings['vpc']['vpc_id']
    subnet_id = settings['vpc']['subnet_id']
    security_group_id = settings['vpc']['security_group_id']
    matlab_mcp_url = settings['matlab_mcp']['url']
    agent_name = settings['agent']['name']
    region = settings['aws']['region']
    
    print(f"   VPC ID:           {vpc_id}")
    print(f"   Subnet ID:        {subnet_id}")
    print(f"   Security Group:   {security_group_id}")
    print(f"   MATLAB MCP URL:   {matlab_mcp_url}")
    print(f"   Agent Name:       {agent_name}")
    
    # Prepare runtime code with MCP URL
    print("\nPreparing runtime code...")
    runtime_file = prepare_runtime_code(matlab_mcp_url)
    
    print(f"\nAWS Region: {region}")
    
    # Initialize AgentCore Runtime
    print("\nInitializing AgentCore Runtime with VPC...")
    agentcore_runtime = Runtime()
    
    # Configure runtime with VPC settings
    print("\nConfiguring runtime...")
    response = agentcore_runtime.configure(
        entrypoint=runtime_file.name,
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region=region,
        agent_name=agent_name,
        vpc_enabled=True,
        vpc_subnets=[subnet_id],
        vpc_security_groups=[security_group_id]
    )
    
    print("   Runtime configured with VPC settings")
    
    # Launch runtime
    print("\nLaunching runtime...")
    launch_result = agentcore_runtime.launch()
    print("   Runtime launched")
    
    # Wait for deployment to complete
    print("\nWaiting for deployment...")
    status_response = agentcore_runtime.status()
    status = status_response.endpoint['status']
    end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
    
    while status not in end_status:
        time.sleep(10)
        status_response = agentcore_runtime.status()
        status = status_response.endpoint['status']
        print(f"   Status: {status}")
    
    print(f"\nFinal status: {status}")
    
    if status == 'READY':
        # Update settings with agent ARN
        agent_arn = launch_result.agent_arn
        settings['agent']['arn'] = agent_arn
        save_settings(settings)
        
        print("\n" + "="*60)
        print("DEPLOYMENT SUCCESSFUL")
        print("="*60)
        print(f"\nAgent ARN: {agent_arn}")
        print(f"\nAgent is deployed in VPC with:")
        print(f"  - Subnet: {subnet_id}")
        print(f"  - Security Group: {security_group_id}")
        print(f"  - MATLAB MCP: {matlab_mcp_url}")
        print(f"\nAuthentication: IAM (no Cognito)")
        
        # Test invocation
        print("\n" + "="*60)
        print("TESTING AGENT")
        print("="*60)
        
        try:
            invoke_response = agentcore_runtime.invoke({
                "prompt": "What tools do you have available?"
            })
            print(f"\nTest response: {invoke_response}")
        except Exception as e:
            print(f"\nTest invocation failed: {e}")
            print("Note: Agent may need IAM permissions to be invoked")
    
    else:
        print("\n" + "="*60)
        print("DEPLOYMENT FAILED")
        print("="*60)
        print(f"Status: {status}")
        print("\nCheck CloudWatch logs for details")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
