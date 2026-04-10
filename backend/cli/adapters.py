"""Adapter management CLI commands."""
import json
import secrets
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient, state, parse_json_arg

adapters_app = typer.Typer(help="Manage bridge adapters")
console = Console()


def _client() -> ApiClient:
    return ApiClient(base_url=state["base_url"])


def _load_config_file(file_path: str) -> dict:
    """Load a JSON config file and return its contents."""
    path = Path(file_path)
    if not path.exists():
        typer.echo(f"Error: File not found: {file_path}", err=True)
        raise SystemExit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: Invalid JSON in {file_path}: {e}", err=True)
        raise SystemExit(1)
    if not isinstance(data, dict):
        typer.echo(f"Error: Expected a JSON object in {file_path}, got {type(data).__name__}", err=True)
        raise SystemExit(1)
    return data


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
                                      help="Adapter type: http, openclaw, python, stdio"),
    config_json: str = typer.Option(None, "--config", "-c", help="Config as JSON string"),
    config_file: str = typer.Option(None, "--config-file", help="Config from a JSON file"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
):
    """Create a new adapter. Use --config for inline JSON or --config-file to load from a file."""
    # Resolve config: --config takes precedence over --config-file
    if config_json is not None:
        config = parse_json_arg(config_json, "--config")
    elif config_file is not None:
        config = _load_config_file(config_file)
    else:
        typer.echo("Error: Either --config or --config-file is required.", err=True)
        raise SystemExit(1)

    if adapter_type == "http" and "auth_token" not in config:
        token = secrets.token_hex(32)
        config["auth_token"] = token
        console.print(f"\n[bold yellow]Auto-generated auth token:[/bold yellow]")
        console.print(f"  {token}\n")
        console.print("[dim]Set this token in your target agent's eval server[/dim]")
        console.print("[dim](e.g., EVAL_AUTH_TOKEN environment variable)[/dim]\n")
    payload = {"name": name, "adapter_type": adapter_type,
               "config": config, "description": description}
    a = _client().post("/api/adapters", json=payload)
    console.print(f"[green]Created adapter #{a['id']}: {a['name']}[/green]")


@adapters_app.command("update")
def update_adapter(
    adapter_id: int = typer.Argument(..., help="Adapter ID"),
    name: str = typer.Option(None, "--name", "-n", help="New adapter name"),
    adapter_type: str = typer.Option(None, "--type", "-t", help="New type: http, openclaw, python, stdio"),
    config_json: str = typer.Option(None, "--config", "-c", help="New config as JSON string"),
    config_file: str = typer.Option(None, "--config-file", help="New config from a JSON file"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
):
    """Update an existing adapter's config. Use --config for inline JSON or --config-file to load from a file."""
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if adapter_type is not None:
        payload["adapter_type"] = adapter_type
    # --config takes precedence over --config-file
    if config_json is not None:
        payload["config"] = parse_json_arg(config_json, "--config")
    elif config_file is not None:
        payload["config"] = _load_config_file(config_file)
    if description is not None:
        payload["description"] = description
    if not payload:
        console.print("[yellow]Nothing to update. Provide at least one option.[/yellow]")
        return
    a = _client().put(f"/api/adapters/{adapter_id}", json=payload)
    console.print(f"[green]Updated adapter #{a['id']}: {a['name']}[/green]")


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
