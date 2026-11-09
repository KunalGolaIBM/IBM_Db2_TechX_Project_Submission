from rich_pyfiglet import RichFiglet
from rich.console import Console

console = Console(markup=False)

def print_banner(title, font="ansi_shadow", colors=["#ff4444", "#ffcc00"], justify="center",):
    _BANNER = RichFiglet(title, font=font, colors=colors, justify=justify)
    console.print(_BANNER)