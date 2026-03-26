"""Scorer template CLI commands (read-only)."""
import json
import typer
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient
from cli.main import state

templates_app = typer.Typer(help="Browse scorer templates (read-only)")
console = Console()


def _client() -> ApiClient:
    return ApiClient(base_url=state["base_url"])


@templates_app.command("list")
def list_templates():
    """List all scorer templates."""
    data = _client().get("/api/scorer-templates")
    if not data:
        console.print("[yellow]No templates found.[/yellow]")
        return
    table = Table(title="Scorer Templates")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Name", style="green")
    table.add_column("Category", style="yellow")
    table.add_column("Format")
    table.add_column("Description")
    for t in data:
        table.add_row(str(t["id"]), t["name"], t.get("category", ""),
                      t.get("output_format", ""), (t.get("description") or "")[:50])
    console.print(table)


@templates_app.command("get")
def get_template(template_id: int = typer.Argument(..., help="Template ID")):
    """Show template details including the copy-paste prompt."""
    t = _client().get(f"/api/scorer-templates/{template_id}")
    console.print(f"[bold cyan]Template #{t['id']}[/bold cyan]: {t['name']}")
    console.print(f"  Category: {t.get('category', '')}")
    console.print(f"  Format: {t.get('output_format', '')}")
    console.print(f"  Description: {t.get('description', '')}")
    console.print(f"\n[bold]Template Prompt (copy this to your coding agent):[/bold]")
    console.print(f"{t.get('template_prompt', '')}")
    if t.get("usage_instructions"):
        console.print(f"\n[bold]Usage Instructions:[/bold]")
        console.print(f"  {t['usage_instructions']}")
    if t.get("example_scorer"):
        console.print(f"\n[bold]Example Scorer JSON:[/bold]")
        console.print(json.dumps(t["example_scorer"], indent=2))
