import random

from google.adk.tools.tool_context import ToolContext


def roll_die(sides: int, tool_context: ToolContext) -> int:
    """Roll a die and return the rolled result.

    Args:
      sides: The integer number of sides the die has.
      tool_context: the tool context
    Returns:
      An integer of the result of rolling the die.
    """
    result = random.randint(1, sides)
    if "rolls" not in tool_context.state:
        tool_context.state["rolls"] = []

    tool_context.state["rolls"] = tool_context.state["rolls"] + [result]
    print(f"current round the result is {result}")
    return result
