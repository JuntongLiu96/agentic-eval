"""Dataset management CLI commands."""
import typer
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient
from cli.main import state

datasets_app = typer.Typer(help="Manage eval datasets and test cases")
console = Console()


def _client() -> ApiClient:
    return ApiClient(base_url=state["base_url"])


@datasets_app.command("list")
def list_datasets():
    """List all datasets."""
    data = _client().get("/api/datasets")
    if not data:
        console.print("[yellow]No datasets found.[/yellow]")
        return
    table = Table(title="Datasets")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Name", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Tags")
    table.add_column("Created")
    for d in data:
        tags = ", ".join(d.get("tags", []) or [])
        created = (d.get("created_at") or "")[:10]
        table.add_row(str(d["id"]), d["name"], d.get("target_type", ""), tags, created)
    console.print(table)


@datasets_app.command("get")
def get_dataset(dataset_id: int = typer.Argument(..., help="Dataset ID")):
    """Show dataset details."""
    d = _client().get(f"/api/datasets/{dataset_id}")
    console.print(f"[bold cyan]Dataset #{d['id']}[/bold cyan]: {d['name']}")
    console.print(f"  Description: {d.get('description', '')}")
    console.print(f"  Type: {d.get('target_type', '')}")
    console.print(f"  Tags: {', '.join(d.get('tags', []) or [])}")
    console.print(f"  Created: {d.get('created_at', '')}")


@datasets_app.command("create")
def create_dataset(
    name: str = typer.Option(..., "--name", "-n", help="Dataset name"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    target_type: str = typer.Option("custom", "--target-type", "-t",
                                     help="Target type: tool, e2e_flow, custom"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
):
    """Create a new dataset."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    payload = {"name": name, "description": description,
               "target_type": target_type, "tags": tag_list}
    d = _client().post("/api/datasets", json=payload)
    console.print(f"[green]Created dataset #{d['id']}: {d['name']}[/green]")


@datasets_app.command("delete")
def delete_dataset(
    dataset_id: int = typer.Argument(..., help="Dataset ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a dataset and all its test cases."""
    if not yes:
        confirm = typer.confirm(f"Delete dataset {dataset_id}?")
        if not confirm:
            raise typer.Abort()
    _client().delete(f"/api/datasets/{dataset_id}")
    console.print(f"[green]Deleted dataset {dataset_id}.[/green]")


@datasets_app.command("import-csv")
def import_csv(
    dataset_id: int = typer.Argument(..., help="Dataset ID to import into"),
    file: str = typer.Option(..., "--file", "-f", help="Path to CSV file"),
):
    """Import test cases from a CSV file into a dataset."""
    result = _client().upload(f"/api/datasets/{dataset_id}/import", file_path=file)
    console.print(f"[green]Imported {result['imported_count']} test cases.[/green]")


@datasets_app.command("export-csv")
def export_csv(
    dataset_id: int = typer.Argument(..., help="Dataset ID to export"),
    output: str = typer.Option("dataset_export.csv", "--output", "-o", help="Output file path"),
):
    """Export test cases from a dataset to a CSV file."""
    _client().download(f"/api/datasets/{dataset_id}/export", output_path=output)
    console.print(f"[green]Exported to {output}[/green]")
