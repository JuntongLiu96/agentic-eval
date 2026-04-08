"""Scorer management CLI commands."""
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
    name: str = typer.Option(..., "--name", "-n", help="Scorer name"),
    eval_prompt: str = typer.Option(..., "--eval-prompt", "-p",
                                     help="Evaluation prompt (includes criteria and score rules)"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    pass_threshold: float = typer.Option(60.0, "--threshold", "-t", help="Pass threshold (score >= this = pass)"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
):
    """Create a new scorer."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    payload = {
        "name": name, "description": description,
        "eval_prompt": eval_prompt, "pass_threshold": pass_threshold, "tags": tag_list,
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
):
    """Update an existing scorer."""
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if eval_prompt is not None:
        payload["eval_prompt"] = eval_prompt
    if description is not None:
        payload["description"] = description
    if pass_threshold is not None:
        payload["pass_threshold"] = pass_threshold
    if tags is not None:
        payload["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if not payload:
        console.print("[yellow]Nothing to update. Provide at least one option.[/yellow]")
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
