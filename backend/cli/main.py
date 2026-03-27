"""AgenticEval CLI entry point."""
import json as json_mod

import typer
from rich.console import Console

from cli.api_client import ApiClient, state

app = typer.Typer(
    name="agenticeval",
    help="AgenticEval — CLI for managing eval datasets, scorers, adapters, and runs.",
    no_args_is_help=True,
)

_console = Console()


@app.callback()
def main(base_url: str = typer.Option("http://localhost:9100", "--base-url", "-u",
                                       help="Backend server URL")):
    """AgenticEval CLI."""
    state["base_url"] = base_url


@app.command("run")
def run_eval(
    dataset: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    scorer: int = typer.Option(..., "--scorer", "-s", help="Scorer ID"),
    adapter: int = typer.Option(..., "--adapter", "-a", help="Adapter ID"),
    name: str = typer.Option("", "--name", "-n", help="Optional run name"),
    judge_config_json: str = typer.Option("{}", "--judge-config",
                                          help="Judge config as JSON string"),
):
    """Create and immediately start an eval run (shortcut)."""
    client = ApiClient(base_url=state["base_url"])
    try:
        judge_config = json_mod.loads(judge_config_json)
    except json_mod.JSONDecodeError:
        _console.print("[red]Invalid JSON in --judge-config[/red]")
        raise typer.Exit(1)
    payload = {"dataset_id": dataset, "scorer_id": scorer, "adapter_id": adapter,
               "name": name, "judge_config": judge_config}
    r = client.post("/api/runs", json=payload)
    run_id = r["id"]
    _console.print(f"[yellow]Created run #{run_id}. Starting...[/yellow]")
    result = client.post(f"/api/runs/{run_id}/start", timeout=3600.0)
    status = result.get("status", "unknown")
    summary = result.get("summary", {})
    _console.print(f"\n[bold]Run #{run_id} completed: {status}[/bold]")
    if summary:
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        rate = summary.get("pass_rate", 0)
        _console.print(f"  Total: {total}, Passed: {passed}, Pass Rate: {rate:.1%}")


from cli.datasets import datasets_app
app.add_typer(datasets_app, name="datasets")

from cli.scorers import scorers_app
app.add_typer(scorers_app, name="scorers")

from cli.adapters import adapters_app
app.add_typer(adapters_app, name="adapters")

from cli.runs import runs_app
app.add_typer(runs_app, name="runs")

from cli.templates import templates_app
app.add_typer(templates_app, name="templates")
