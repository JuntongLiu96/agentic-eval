"""Scorer management CLI commands."""
import json
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient, state

scorers_app = typer.Typer(help="Manage scorers (evaluation criteria)")
console = Console()


def _client() -> ApiClient:
    return ApiClient(base_url=state["base_url"])


def _load_scorer_file(file_path: str) -> dict:
    """Load a scorer JSON file and return its contents."""
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


@scorers_app.command("list")
def list_scorers():
    """List all scorers."""
    data = _client().get("/api/scorers")
    if not data:
        console.print("[yellow]No scorers found.[/yellow]")
        return
    table = Table(title="Scorers")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Name", style="green")
    table.add_column("Threshold", style="yellow")
    table.add_column("Tags")
    table.add_column("Created")
    for s in data:
        tags = ", ".join(s.get("tags", []) or [])
        created = (s.get("created_at") or "")[:10]
        threshold = str(s.get("pass_threshold", "60")) if s.get("pass_threshold") else "60"
        table.add_row(str(s["id"]), s["name"], threshold, tags, created)
    console.print(table)


@scorers_app.command("get")
def get_scorer(scorer_id: int = typer.Argument(..., help="Scorer ID")):
    """Show scorer details including eval prompt."""
    s = _client().get(f"/api/scorers/{scorer_id}")
    console.print(f"[bold cyan]Scorer #{s['id']}[/bold cyan]: {s['name']}")
    console.print(f"  Description: {s.get('description', '')}")
    console.print(f"  Pass Threshold: {s.get('pass_threshold', 60)}")
    console.print(f"  Tags: {', '.join(s.get('tags', []) or [])}")
    console.print(f"\n[bold]Eval Prompt:[/bold]")
    console.print(s.get('eval_prompt', ''))


@scorers_app.command("create")
def create_scorer(
    name: str = typer.Option(None, "--name", "-n", help="Scorer name"),
    eval_prompt: str = typer.Option(None, "--eval-prompt", "-p",
                                     help="Evaluation prompt (includes criteria and score rules)"),
    description: str = typer.Option(None, "--description", "-d", help="Description"),
    pass_threshold: float = typer.Option(None, "--threshold", "-t", help="Pass threshold (score >= this = pass)"),
    tags: str = typer.Option(None, "--tags", help="Comma-separated tags"),
    file: str = typer.Option(None, "--file", "-f", help="JSON file with scorer definition (name, eval_prompt, etc.)"),
):
    """Create a new scorer. Use --file to load from a JSON file, or pass fields as options."""
    # Start from file if provided, then overlay CLI options
    base: dict = {}
    if file:
        base = _load_scorer_file(file)

    # CLI options override file values
    if name is not None:
        base["name"] = name
    if eval_prompt is not None:
        base["eval_prompt"] = eval_prompt
    if description is not None:
        base["description"] = description
    if pass_threshold is not None:
        base["pass_threshold"] = pass_threshold
    if tags is not None:
        base["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    # Apply defaults
    base.setdefault("description", "")
    base.setdefault("pass_threshold", 60.0)
    if isinstance(base.get("tags"), list):
        pass  # already a list
    elif isinstance(base.get("tags"), str):
        base["tags"] = [t.strip() for t in base["tags"].split(",") if t.strip()]
    else:
        base.setdefault("tags", [])

    # Validate required fields
    if not base.get("name"):
        typer.echo("Error: --name is required (or provide 'name' in the JSON file).", err=True)
        raise SystemExit(1)
    if not base.get("eval_prompt"):
        typer.echo("Error: --eval-prompt is required (or provide 'eval_prompt' in the JSON file).", err=True)
        raise SystemExit(1)

    payload = {
        "name": base["name"],
        "description": base["description"],
        "eval_prompt": base["eval_prompt"],
        "pass_threshold": base["pass_threshold"],
        "tags": base["tags"],
    }
    s = _client().post("/api/scorers", json=payload)
    console.print(f"[green]Created scorer #{s['id']}: {s['name']}[/green]")


@scorers_app.command("update")
def update_scorer(
    scorer_id: int = typer.Argument(..., help="Scorer ID"),
    name: str = typer.Option(None, "--name", "-n", help="New scorer name"),
    eval_prompt: str = typer.Option(None, "--eval-prompt", "-p", help="New eval prompt"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    pass_threshold: float = typer.Option(None, "--threshold", "-t", help="New pass threshold"),
    tags: str = typer.Option(None, "--tags", help="New comma-separated tags"),
    file: str = typer.Option(None, "--file", "-f", help="JSON file with scorer fields to update"),
):
    """Update an existing scorer. Use --file to load from a JSON file, CLI options override file values."""
    # Start from file if provided, then overlay CLI options
    base: dict = {}
    if file:
        base = _load_scorer_file(file)

    # CLI options override file values
    if name is not None:
        base["name"] = name
    if eval_prompt is not None:
        base["eval_prompt"] = eval_prompt
    if description is not None:
        base["description"] = description
    if pass_threshold is not None:
        base["pass_threshold"] = pass_threshold
    if tags is not None:
        base["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    # Convert tags if from file
    if "tags" in base and isinstance(base["tags"], str):
        base["tags"] = [t.strip() for t in base["tags"].split(",") if t.strip()]

    # Build payload — only include fields that were set
    payload: dict = {}
    for key in ("name", "eval_prompt", "description", "pass_threshold", "tags"):
        if key in base:
            payload[key] = base[key]

    if not payload:
        console.print("[yellow]Nothing to update. Provide at least one option or --file.[/yellow]")
        return
    s = _client().put(f"/api/scorers/{scorer_id}", json=payload)
    console.print(f"[green]Updated scorer #{s['id']}: {s['name']}[/green]")


@scorers_app.command("delete")
def delete_scorer(
    scorer_id: int = typer.Argument(..., help="Scorer ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a scorer."""
    if not yes:
        confirm = typer.confirm(f"Delete scorer {scorer_id}?")
        if not confirm:
            raise typer.Abort()
    _client().delete(f"/api/scorers/{scorer_id}")
    console.print(f"[green]Deleted scorer {scorer_id}.[/green]")
