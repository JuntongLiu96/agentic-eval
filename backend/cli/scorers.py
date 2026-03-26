"""Scorer management CLI commands."""
import json
import typer
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient, state

scorers_app = typer.Typer(help="Manage scorers (evaluation criteria)")
console = Console()


def _client() -> ApiClient:
    return ApiClient(base_url=state["base_url"])


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
    table.add_column("Format", style="yellow")
    table.add_column("Tags")
    table.add_column("Created")
    for s in data:
        tags = ", ".join(s.get("tags", []) or [])
        created = (s.get("created_at") or "")[:10]
        table.add_row(str(s["id"]), s["name"], s.get("output_format", ""), tags, created)
    console.print(table)


@scorers_app.command("get")
def get_scorer(scorer_id: int = typer.Argument(..., help="Scorer ID")):
    """Show scorer details including eval prompt and criteria."""
    s = _client().get(f"/api/scorers/{scorer_id}")
    console.print(f"[bold cyan]Scorer #{s['id']}[/bold cyan]: {s['name']}")
    console.print(f"  Description: {s.get('description', '')}")
    console.print(f"  Format: {s.get('output_format', '')}")
    console.print(f"  Threshold: {s.get('pass_threshold', 'default')}")
    console.print(f"  Tags: {', '.join(s.get('tags', []) or [])}")
    console.print(f"\n[bold]Eval Prompt:[/bold]")
    console.print(f"  {s.get('eval_prompt', '')}")
    if s.get("criteria"):
        console.print(f"\n[bold]Criteria:[/bold]")
        console.print(f"  {json.dumps(s['criteria'], indent=2)}")


@scorers_app.command("create")
def create_scorer(
    name: str = typer.Option(..., "--name", "-n", help="Scorer name"),
    output_format: str = typer.Option(..., "--output-format", "-f",
                                       help="Output format: binary, numeric, rubric"),
    eval_prompt: str = typer.Option(..., "--eval-prompt", "-p", help="Evaluation prompt"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    criteria_json: str = typer.Option("{}", "--criteria", help="Criteria as JSON string"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
):
    """Create a new scorer."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    try:
        criteria = json.loads(criteria_json)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON in --criteria[/red]", err=True)
        raise typer.Exit(1)
    payload = {
        "name": name, "description": description, "output_format": output_format,
        "eval_prompt": eval_prompt, "criteria": criteria, "tags": tag_list,
    }
    s = _client().post("/api/scorers", json=payload)
    console.print(f"[green]Created scorer #{s['id']}: {s['name']}[/green]")


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
