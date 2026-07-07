"""
Prettify the execution information of the graph using Rich for professional output.
"""

from typing import Union
from rich.console import Console
from rich.table import Table


def prettify_exec_info(
    complete_result: list[dict], as_string: bool = True
) -> Union[str, list[dict]]:
    """
    Formats the execution information of a graph showing node statistics using Rich.
    """
    if not as_string:
        return complete_result

    if not complete_result:
        return "Empty result"

    console = Console()
    table = Table(title="[bold cyan]Graph Node Statistics[/bold cyan]")

    table.add_column("Node", style="magenta")
    table.add_column("Tokens", justify="right", style="green")
    table.add_column("Prompt", justify="right", style="green")
    table.add_column("Compl.", justify="right", style="green")
    table.add_column("Requests", justify="right", style="blue")
    table.add_column("Cost ($)", justify="right", style="yellow")
    table.add_column("Time (s)", justify="right", style="red")

    for item in complete_result:
        table.add_row(
            item["node_name"],
            str(item["total_tokens"]),
            str(item["prompt_tokens"]),
            str(item["completion_tokens"]),
            str(item["successful_requests"]),
            f"{item['total_cost_USD']:.4f}",
            f"{item['exec_time']:.2f}"
        )

    console.print(table)
    return "Table printed to console"
