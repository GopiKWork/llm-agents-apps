#!/usr/bin/env python3
"""
Invoke VPC-deployed agent using bedrock-agentcore client
"""

import json
import boto3
from pathlib import Path

def load_settings():
    """Load settings including agent ARN"""
    settings_file = Path(__file__).parent / "settings.json"
    
    if not settings_file.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_file}")
    
    with open(settings_file, 'r') as f:
        return json.load(f)

def invoke_agent(prompt):
    """Invoke agent using bedrock-agentcore client"""
    settings = load_settings()
    agent_arn = settings['agent'].get('arn')
    region = settings['aws'].get('region', 'us-west-2')
    
    if not agent_arn:
        raise ValueError("Agent ARN not found in settings. Run setup_vpc_agent.py first.")
    
    # Use bedrock-agentcore client
    agentcore_client = boto3.client('bedrock-agentcore', region_name=region)
    
    # Invoke agent runtime with streaming
    boto3_response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt})
    )
    
    # Check if the response is streaming
    if "text/event-stream" in boto3_response.get("contentType", ""):
        print("Agent: ", end='', flush=True)
        content = []
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data = line[6:].replace('"', '')  # Remove "data: " prefix
                    print(data, end='', flush=True)
                    content.append(data.replace('"', ''))
        
        # Display the complete streamed response
        full_response = " ".join(content)
        print()  # New line after streaming
        return full_response
    else:
        # Handle non-streaming response
        try:
            events = []
            for event in boto3_response.get("response", []):
                events.append(event)
        except Exception as e:
            events = [f"Error reading EventStream: {e}"]
        
        if events:
            try:
                response_data = json.loads(events[0].decode("utf-8"))
                print(response_data)
                return response_data
            except:
                print(f"Raw response: {events[0]}")
                return events[0]

def main():
    import sys
    
    # Sample prompts for user selection
    sample_prompts = [
        "Calculate the mean and standard deviation of [15, 23, 18, 42, 31, 28, 19]",
        "Solve the quadratic equation 2x^2 + 5x - 3 = 0",
        "Generate 10 evenly spaced numbers between 0 and 100",
        "Convert 75 degrees Fahrenheit to Celsius",
        "Calculate the mean of [68, 72, 75, 70, 73] in Fahrenheit, then convert to Celsius",
        "Generate 5 numbers from 1 to 9, use first three as coefficients for quadratic equation",
        "Find max and min in [12, 18, 24, 30, 36], then calculate their GCD and LCM",
        "Calculate sin(π/6) and cos(π/6), then find what percentage sine is of cosine",
        "Evaluate polynomial [1, -2, 1] at x=5, then calculate factorial of the result",
        "Generate 10 numbers from 0 to 100, find mean and std, convert mean to Celsius, find std as percentage of mean"
    ]
    
    # Check if prompt provided as argument
    if len(sys.argv) >= 2:
        # Single invocation mode
        prompt = ' '.join(sys.argv[1:])
        try:
            invoke_agent(prompt)
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        return
    
    # Interactive loop mode
    print("="*60)
    print("NUMERICAL SOLVER AGENT - INTERACTIVE MODE")
    print("="*60)
    print("\nSample prompts (enter number to use, or type your own):")
    print()
    
    for i, prompt in enumerate(sample_prompts, 1):
        print(f"{i:2d}. {prompt}")
    
    print(f"\n{'0':>2}. Enter custom prompt")
    print(f"{'q':>2}. Quit")
    print("\n" + "="*60 + "\n")
    
    try:
        settings = load_settings()
        agent_name = settings['agent'].get('name')
        agent_arn = settings['agent'].get('arn')
        
        if not agent_arn:
            print("Error: Agent ARN not found in settings. Run setup_agent.py first.")
            return
        
        print(f"Connected to: {agent_name}")
        print(f"ARN: {agent_arn}\n")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"Error loading settings: {e}")
        return
    
    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = input("Select prompt number or enter custom (q to quit): ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break
            
            # Check if it's a number selection
            if user_input.isdigit():
                selection = int(user_input)
                if selection == 0:
                    prompt = input("\nEnter your prompt: ").strip()
                    if not prompt:
                        continue
                elif 1 <= selection <= len(sample_prompts):
                    prompt = sample_prompts[selection - 1]
                    print(f"\nSelected: {prompt}")
                else:
                    print(f"Invalid selection. Please choose 0-{len(sample_prompts)}")
                    continue
            else:
                # Treat as custom prompt
                prompt = user_input
            
            # Skip empty prompts
            if not prompt:
                continue
            
            # Invoke agent
            print()
            invoke_agent(prompt)
            print()
            
        except KeyboardInterrupt:
            print("\n\nSession ended by user. Goodbye!")
            break
        except EOFError:
            print("\n\nSession ended. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            print()

if __name__ == "__main__":
    main()
