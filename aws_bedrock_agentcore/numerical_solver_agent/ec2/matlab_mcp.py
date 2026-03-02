# matlab_mcp.py
from mcp.server.fastmcp import FastMCP
import math
from typing import List, Union

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

@mcp.tool()
def linspace(start: float, stop: float, num: int = 50) -> List[float]:
    """Generate linearly spaced vector between start and stop values
    
    Args:
        start: Starting value
        stop: Ending value
        num: Number of points to generate (default: 50)
    
    Returns:
        List of evenly spaced values
    """
    print(f"[TOOL CALL] linspace with args: start={start}, stop={stop}, num={num}")
    if num < 2:
        return [start]
    step = (stop - start) / (num - 1)
    return [start + step * i for i in range(num)]

@mcp.tool()
def mean(data: List[float]) -> float:
    """Calculate the mean (average) of array elements
    
    Args:
        data: List of numbers
    
    Returns:
        Mean value
    """
    print(f"[TOOL CALL] mean with args: data={data}")
    if not data:
        return 0.0
    return sum(data) / len(data)

@mcp.tool()
def std(data: List[float]) -> float:
    """Calculate the standard deviation of array elements
    
    Args:
        data: List of numbers
    
    Returns:
        Standard deviation
    """
    print(f"[TOOL CALL] std with args: data={data}")
    if len(data) < 2:
        return 0.0
    m = mean(data)
    variance = sum((x - m) ** 2 for x in data) / (len(data) - 1)
    return math.sqrt(variance)

@mcp.tool()
def max_value(data: List[float]) -> float:
    """Find maximum value in array
    
    Args:
        data: List of numbers
    
    Returns:
        Maximum value
    """
    print(f"[TOOL CALL] max_value with args: data={data}")
    return max(data) if data else float('-inf')

@mcp.tool()
def min_value(data: List[float]) -> float:
    """Find minimum value in array
    
    Args:
        data: List of numbers
    
    Returns:
        Minimum value
    """
    print(f"[TOOL CALL] min_value with args: data={data}")
    return min(data) if data else float('inf')

@mcp.tool()
def sum_array(data: List[float]) -> float:
    """Sum of array elements
    
    Args:
        data: List of numbers
    
    Returns:
        Sum of all elements
    """
    print(f"[TOOL CALL] sum_array with args: data={data}")
    return sum(data)

@mcp.tool()
def prod(data: List[float]) -> float:
    """Product of array elements
    
    Args:
        data: List of numbers
    
    Returns:
        Product of all elements
    """
    print(f"[TOOL CALL] prod with args: data={data}")
    result = 1.0
    for x in data:
        result *= x
    return result

@mcp.tool()
def sqrt_value(x: float) -> float:
    """Square root of value
    
    Args:
        x: Input value
    
    Returns:
        Square root
    """
    print(f"[TOOL CALL] sqrt_value with args: x={x}")
    return math.sqrt(x)

@mcp.tool()
def abs_value(x: float) -> float:
    """Absolute value
    
    Args:
        x: Input value
    
    Returns:
        Absolute value
    """
    print(f"[TOOL CALL] abs_value with args: x={x}")
    return abs(x)

@mcp.tool()
def sin_value(x: float) -> float:
    """Sine of argument in radians
    
    Args:
        x: Angle in radians
    
    Returns:
        Sine value
    """
    print(f"[TOOL CALL] sin_value with args: x={x}")
    return math.sin(x)

@mcp.tool()
def cos_value(x: float) -> float:
    """Cosine of argument in radians
    
    Args:
        x: Angle in radians
    
    Returns:
        Cosine value
    """
    print(f"[TOOL CALL] cos_value with args: x={x}")
    return math.cos(x)

@mcp.tool()
def exp_value(x: float) -> float:
    """Exponential function (e^x)
    
    Args:
        x: Exponent value
    
    Returns:
        e raised to power x
    """
    print(f"[TOOL CALL] exp_value with args: x={x}")
    return math.exp(x)

@mcp.tool()
def log_value(x: float) -> float:
    """Natural logarithm
    
    Args:
        x: Input value (must be positive)
    
    Returns:
        Natural logarithm of x
    """
    print(f"[TOOL CALL] log_value with args: x={x}")
    return math.log(x)

@mcp.tool()
def polyval(coefficients: List[float], x: float) -> float:
    """Evaluate polynomial at specific value
    
    Args:
        coefficients: Polynomial coefficients in descending order [a_n, ..., a_1, a_0]
        x: Value at which to evaluate polynomial
    
    Returns:
        Polynomial value at x
    """
    print(f"[TOOL CALL] polyval with args: coefficients={coefficients}, x={x}")
    result = 0.0
    for coef in coefficients:
        result = result * x + coef
    return result

@mcp.tool()
def diff(data: List[float]) -> List[float]:
    """Calculate differences between consecutive elements
    
    Args:
        data: List of numbers
    
    Returns:
        List of differences
    """
    print(f"[TOOL CALL] diff with args: data={data}")
    if len(data) < 2:
        return []
    return [data[i+1] - data[i] for i in range(len(data) - 1)]

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
