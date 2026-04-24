"""Dataset management CLI commands."""
import json
import typer
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient, state, parse_json_arg

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


@datasets_app.command("update")
def update_dataset(
    dataset_id: int = typer.Argument(..., help="Dataset ID"),
    name: str = typer.Option(None, "--name", "-n", help="New name"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    target_type: str = typer.Option(None, "--target-type", "-t", help="New target type"),
    tags: str = typer.Option(None, "--tags", help="New comma-separated tags"),
):
    """Update an existing dataset."""
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if target_type is not None:
        payload["target_type"] = target_type
    if tags is not None:
        payload["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if not payload:
        console.print("[yellow]Nothing to update. Provide at least one option.[/yellow]")
        return
    d = _client().put(f"/api/datasets/{dataset_id}", json=payload)
    console.print(f"[green]Updated dataset #{d['id']}: {d['name']}[/green]")


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


@datasets_app.command("add-case")
def add_case(
    dataset_id: int = typer.Argument(..., help="Dataset ID to add the test case to"),
    name: str = typer.Option(..., "--name", "-n", help="Test case name"),
    prompt: str = typer.Option(None, "--prompt", "-p", help="User prompt (single-turn)"),
    data: str = typer.Option(None, "--data", help='Test data as JSON (for multi-turn: \'{"turns": [...]}\')'  ),
    expected: str = typer.Option(..., "--expected", "-e",
                                  help="Expected result as JSON string (e.g. '{\"answer\": \"4\"}')"),
):
    """Add a single test case to a dataset.

    For single-turn: use --prompt "your prompt here"
    For multi-turn:  use --data '{"turns": [{"prompt": "msg1"}, {"prompt": "msg2"}]}'
    """
    if prompt and data:
        console.print("[red]Cannot use both --prompt and --data. Use --prompt for single-turn or --data for multi-turn.[/red]")
        raise typer.Exit(code=1)
    if not prompt and not data:
        console.print("[red]Provide either --prompt (single-turn) or --data (multi-turn).[/red]")
        raise typer.Exit(code=1)

    expected_parsed = parse_json_arg(expected, "--expected")
    if prompt:
        test_data = {"prompt": prompt}
    else:
        test_data = parse_json_arg(data, "--data")

    payload = {
        "name": name,
        "data": test_data,
        "expected_result": expected_parsed,
    }
    tc = _client().post(f"/api/datasets/{dataset_id}/testcases", json=payload)
    console.print(f"[green]Added test case #{tc['id']}: {tc['name']}[/green]")


@datasets_app.command("list-cases")
def list_cases(dataset_id: int = typer.Argument(..., help="Dataset ID")):
    """List all test cases in a dataset."""
    data = _client().get(f"/api/datasets/{dataset_id}/testcases")
    if not data:
        console.print("[yellow]No test cases found.[/yellow]")
        return
    table = Table(title=f"Test Cases (Dataset #{dataset_id})")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Name", style="green")
    table.add_column("Type", width=8)
    table.add_column("Prompt / Turns")
    table.add_column("Expected Result")
    for tc in data:
        prompt_data = tc.get("data", {})
        if isinstance(prompt_data, dict) and "turns" in prompt_data:
            turns = prompt_data["turns"]
            type_str = f"[cyan]{len(turns)}-turn[/cyan]"
            prompt_str = turns[0].get("prompt", "") if turns else ""
        else:
            type_str = "single"
            prompt_str = prompt_data.get("prompt", json.dumps(prompt_data)) if isinstance(prompt_data, dict) else str(prompt_data)
        expected_str = json.dumps(tc.get("expected_result", {}))
        table.add_row(
            str(tc["id"]),
            tc["name"],
            type_str,
            prompt_str[:50] + ("..." if len(prompt_str) > 50 else ""),
            expected_str[:50] + ("..." if len(expected_str) > 50 else ""),
        )
    console.print(table)


@datasets_app.command("update-case")
def update_case(
    testcase_id: int = typer.Argument(..., help="Test case ID"),
    name: str = typer.Option(None, "--name", "-n", help="New name"),
    prompt: str = typer.Option(None, "--prompt", "-p", help="New prompt (single-turn)"),
    data: str = typer.Option(None, "--data", help='New test data as JSON (for multi-turn)'),
    expected: str = typer.Option(None, "--expected", "-e", help="New expected result (JSON)"),
):
    """Update an existing test case."""
    if prompt and data:
        console.print("[red]Cannot use both --prompt and --data.[/red]")
        raise typer.Exit(code=1)
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if prompt is not None:
        payload["data"] = {"prompt": prompt}
    if data is not None:
        payload["data"] = parse_json_arg(data, "--data")
    if expected is not None:
        payload["expected_result"] = parse_json_arg(expected, "--expected")
    if not payload:
        console.print("[yellow]Nothing to update. Provide at least one option.[/yellow]")
        return
    tc = _client().put(f"/api/testcases/{testcase_id}", json=payload)
    console.print(f"[green]Updated test case #{tc['id']}: {tc['name']}[/green]")


@datasets_app.command("delete-case")
def delete_case(
    testcase_id: int = typer.Argument(..., help="Test case ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a single test case."""
    if not yes:
        confirm = typer.confirm(f"Delete test case {testcase_id}?")
        if not confirm:
            raise typer.Abort()
    _client().delete(f"/api/testcases/{testcase_id}")
    console.print(f"[green]Deleted test case {testcase_id}.[/green]")
