"""Adapter management CLI commands."""
import json
import typer
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient, state

adapters_app = typer.Typer(help="Manage bridge adapters")
console = Console()


def _client() -> ApiClient:
    return ApiClient(base_url=state["base_url"])


@adapters_app.command("list")
def list_adapters():
    """List all adapters."""
    data = _client().get("/api/adapters")
    if not data:
        console.print("[yellow]No adapters found.[/yellow]")
        return
    table = Table(title="Adapters")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Name", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Description")
    table.add_column("Created")
    for a in data:
        created = (a.get("created_at") or "")[:10]
        table.add_row(str(a["id"]), a["name"], a.get("adapter_type", ""),
                      a.get("description", ""), created)
    console.print(table)


@adapters_app.command("get")
def get_adapter(adapter_id: int = typer.Argument(..., help="Adapter ID")):
    """Show adapter details including config."""
    a = _client().get(f"/api/adapters/{adapter_id}")
    console.print(f"[bold cyan]Adapter #{a['id']}[/bold cyan]: {a['name']}")
    console.print(f"  Type: {a.get('adapter_type', '')}")
    console.print(f"  Description: {a.get('description', '')}")
    console.print(f"  Created: {a.get('created_at', '')}")
    console.print(f"\n[bold]Config:[/bold]")
    config = a.get("config", {})
    console.print(f"  {json.dumps(config, indent=2)}")


@adapters_app.command("create")
def create_adapter(
    name: str = typer.Option(..., "--name", "-n", help="Adapter name"),
    adapter_type: str = typer.Option(..., "--type", "-t",
                                      help="Adapter type: http, python, stdio"),
    config_json: str = typer.Option(..., "--config", "-c", help="Config as JSON string"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
):
    """Create a new adapter."""
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON in --config[/red]", err=True)
        raise typer.Exit(1)
    payload = {"name": name, "adapter_type": adapter_type,
               "config": config, "description": description}
    a = _client().post("/api/adapters", json=payload)
    console.print(f"[green]Created adapter #{a['id']}: {a['name']}[/green]")


@adapters_app.command("delete")
def delete_adapter(
    adapter_id: int = typer.Argument(..., help="Adapter ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete an adapter."""
    if not yes:
        confirm = typer.confirm(f"Delete adapter {adapter_id}?")
        if not confirm:
            raise typer.Abort()
    _client().delete(f"/api/adapters/{adapter_id}")
    console.print(f"[green]Deleted adapter {adapter_id}.[/green]")


@adapters_app.command("check")
def health_check(adapter_id: int = typer.Argument(..., help="Adapter ID")):
    """Run a health check on an adapter."""
    result = _client().post(f"/api/adapters/{adapter_id}/health")
    if result.get("healthy"):
        console.print(f"[green]✓ Adapter {adapter_id} is healthy.[/green]")
    else:
        error = result.get("error", "Unknown error")
        console.print(f"[red]✗ Adapter {adapter_id} is unhealthy: {error}[/red]")
