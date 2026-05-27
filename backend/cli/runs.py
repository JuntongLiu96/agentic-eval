"""Eval run management CLI commands."""
import json
import typer
from rich.console import Console
from rich.table import Table
from cli.api_client import ApiClient, state, parse_json_arg

runs_app = typer.Typer(help="Manage eval runs")
console = Console()


def _client() -> ApiClient:
    return ApiClient(base_url=state["base_url"])


@runs_app.command("comparison")
def comparison(
    baseline: int = typer.Option(..., "--compare-baseline", help="Cold-baseline run ID"),
    warm: int = typer.Option(..., "--warm", help="Warm (memory-augmented) run ID"),
    metrics: str = typer.Option("n_reduction", "--metrics",
                                 help="Comma-separated metric names"),
):
    """AE-5: Compare a cold baseline run vs a warm run; print delta metrics."""
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    result = _client().post("/api/runs/comparison", json={
        "baseline_run_id": baseline, "warm_run_id": warm, "metrics": metric_list,
    })
    table = Table(title=f"Comparison: baseline #{baseline} vs warm #{warm}")
    table.add_column("Test Case", style="cyan")
    for m in metric_list:
        table.add_column(m, style="green")
    for pair in result.get("pairs", []):
        row = [str(pair["test_case_id"])]
        for m in metric_list:
            v = pair["deltas"].get(m)
            row.append(f"{v:.3f}" if isinstance(v, (int, float)) else "—")
        table.add_row(*row)
    console.print(table)


@runs_app.command("list")
def list_runs():
    """List all eval runs."""
    data = _client().get("/api/runs")
    if not data:
        console.print("[yellow]No runs found.[/yellow]")
        return
    table = Table(title="Eval Runs")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Name", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Dataset", width=8)
    table.add_column("Scorer", width=8)
    table.add_column("Adapter", width=8)
    table.add_column("Created")
    for r in data:
        created = (r.get("created_at") or "")[:10]
        table.add_row(str(r["id"]), r.get("name", ""), r.get("status", ""),
                      str(r.get("dataset_id", "")), str(r.get("scorer_id", "")),
                      str(r.get("adapter_id", "")), created)
    console.print(table)


@runs_app.command("get")
def get_run(run_id: int = typer.Argument(..., help="Run ID")):
    """Show eval run details."""
    r = _client().get(f"/api/runs/{run_id}")
    console.print(f"[bold cyan]Run #{r['id']}[/bold cyan]: {r.get('name', '(unnamed)')}")
    console.print(f"  Status: {r.get('status', '')}")
    console.print(f"  Dataset ID: {r.get('dataset_id', '')}")
    console.print(f"  Scorer ID: {r.get('scorer_id', '')}")
    console.print(f"  Adapter ID: {r.get('adapter_id', '')}")
    console.print(f"  Created: {r.get('created_at', '')}")
    if r.get("started_at"):
        console.print(f"  Started: {r['started_at']}")
    if r.get("finished_at"):
        console.print(f"  Finished: {r['finished_at']}")
    if r.get("judge_config"):
        console.print(f"\n[bold]Judge Config:[/bold]")
        console.print(f"  {json.dumps(r['judge_config'], indent=2)}")


@runs_app.command("create")
def create_run(
    dataset: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    scorer: int = typer.Option(..., "--scorer", "-s", help="Scorer ID (default scorer)"),
    adapter: int = typer.Option(..., "--adapter", "-a", help="Adapter ID"),
    name: str = typer.Option("", "--name", "-n", help="Optional run name"),
    extra_scorers: str = typer.Option("", "--scorer-ids",
                                       help="AE-13: comma-separated extra scorer IDs (run alongside --scorer)"),
    judge_config_json: str = typer.Option("{}", "--judge-config",
                                          help="Judge config as JSON string"),
    num_rounds: int = typer.Option(1, "--num-rounds", "-r", help="Number of rounds (default: 1)"),
    round_mode: str = typer.Option("agent", "--round-mode", help="Round mode: agent or scorer"),
):
    """Create a new eval run (does not start it)."""
    judge_config = parse_json_arg(judge_config_json, "--judge-config")
    scorer_ids: list[int] = []
    if extra_scorers.strip():
        try:
            scorer_ids = [int(x.strip()) for x in extra_scorers.split(",") if x.strip()]
        except ValueError:
            raise typer.BadParameter("--scorer-ids must be a comma-separated list of integers")
    payload = {"dataset_id": dataset, "scorer_id": scorer, "adapter_id": adapter,
               "name": name, "scorer_ids": scorer_ids, "judge_config": judge_config,
               "num_rounds": num_rounds, "round_mode": round_mode}
    r = _client().post("/api/runs", json=payload)
    rounds_info = f", {r.get('num_rounds', 1)} rounds ({r.get('round_mode', 'agent')})" if r.get('num_rounds', 1) > 1 else ""
    extra_info = f", +{len(scorer_ids)} extra scorers" if scorer_ids else ""
    console.print(f"[green]Created run #{r['id']}: {r.get('name', '')} (status: {r.get('status', 'pending')}{rounds_info}{extra_info})[/green]")


@runs_app.command("delete")
def delete_run(
    run_id: int = typer.Argument(..., help="Run ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete an eval run and all its results."""
    if not yes:
        confirm = typer.confirm(f"Delete run {run_id} and all its results?")
        if not confirm:
            raise typer.Abort()
    _client().delete(f"/api/runs/{run_id}")
    console.print(f"[green]Deleted run {run_id}.[/green]")


@runs_app.command("start")
def start_run(run_id: int = typer.Argument(..., help="Run ID to start")):
    """Start an eval run. Blocks until the run completes."""
    console.print(f"[yellow]Starting run {run_id}... (this may take a while)[/yellow]")
    result = _client().post(f"/api/runs/{run_id}/start", timeout=3600.0)
    status = result.get("status", "unknown")
    summary = result.get("summary", {})
    console.print(f"\n[bold]Run completed: {status}[/bold]")
    if summary:
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        rate = summary.get("pass_rate", 0)
        console.print(f"  Total: {total}, Passed: {passed}, Pass Rate: {rate:.1f}%")


@runs_app.command("results")
def show_results(
    run_id: int = typer.Argument(..., help="Run ID"),
    round_num: int = typer.Option(None, "--round", "-R", help="Filter by round number"),
):
    """Show detailed results for a run."""
    params = {}
    if round_num is not None:
        params["round"] = round_num
    data = _client().get(f"/api/runs/{run_id}/results", params=params)
    if not data:
        console.print("[yellow]No results found.[/yellow]")
        return
    table = Table(title=f"Results for Run #{run_id}")
    table.add_column("TC ID", style="cyan", width=6)
    table.add_column("Scorer", width=7)
    table.add_column("Passed", width=8)
    table.add_column("Duration (ms)", width=14)
    table.add_column("Reasoning")
    for r in data:
        passed_str = "[green]\u2713[/green]" if r.get("passed") else "[red]\u2717[/red]"
        reasoning = (r.get("judge_reasoning") or "")[:60]
        table.add_row(str(r.get("test_case_id", "")),
                      str(r.get("scorer_id") or "-"), passed_str,
                      str(r.get("duration_ms", "")), reasoning)
    console.print(table)


@runs_app.command("per-scorer")
def per_scorer(run_id: int = typer.Argument(..., help="Run ID")):
    """AE-13: show per-scorer aggregates for a multi-scorer run."""
    data = _client().get(f"/api/runs/{run_id}/per-scorer")
    if not data:
        console.print("[yellow]No results found.[/yellow]")
        return
    table = Table(title=f"Per-scorer aggregates for Run #{run_id}")
    table.add_column("Scorer", style="cyan")
    table.add_column("ID", width=5)
    table.add_column("Total", width=7)
    table.add_column("Passed", width=7)
    table.add_column("Pass rate", width=10)
    table.add_column("Avg score", width=10)
    for name, b in data.items():
        rate = b.get("pass_rate", 0)
        avg = b.get("avg_score")
        table.add_row(name, str(b.get("scorer_id") or "-"),
                      str(b.get("total", 0)), str(b.get("passed", 0)),
                      f"{rate:.1f}%", f"{avg:.2f}" if isinstance(avg, (int, float)) else "\u2014")
    console.print(table)


@runs_app.command("compare")
def compare_runs(
    run1: int = typer.Argument(..., help="First run ID"),
    run2: int = typer.Argument(..., help="Second run ID"),
):
    """Compare two eval runs side by side."""
    data = _client().get("/api/runs/compare", params={"run1": run1, "run2": run2})
    s1 = data.get("run1", {}).get("summary", {})
    s2 = data.get("run2", {}).get("summary", {})

    console.print(f"\n[bold]Run 1 (#{run1}):[/bold] {s1.get('passed', 0)}/{s1.get('total', 0)} passed "
                  f"({s1.get('pass_rate', 0):.1f}%)")
    console.print(f"[bold]Run 2 (#{run2}):[/bold] {s2.get('passed', 0)}/{s2.get('total', 0)} passed "
                  f"({s2.get('pass_rate', 0):.1f}%)")

    comparisons = data.get("comparisons", [])
    if comparisons:
        table = Table(title="Per-Test-Case Comparison")
        table.add_column("TC ID", style="cyan")
        table.add_column("Run 1", width=8)
        table.add_column("Run 2", width=8)
        table.add_column("Changed?", width=10)
        for c in comparisons:
            r1_str = "[green]\u2713[/green]" if c.get("run1_passed") else "[red]\u2717[/red]"
            r2_str = "[green]\u2713[/green]" if c.get("run2_passed") else "[red]\u2717[/red]"
            changed = "[yellow]YES[/yellow]" if c.get("changed") else ""
            table.add_row(str(c.get("test_case_id", "")), r1_str, r2_str, changed)
        console.print(table)


@runs_app.command("export")
def export_run(
    run_id: int = typer.Argument(..., help="Run ID to export"),
    output: str = typer.Option("run_results.csv", "--output", "-o", help="Output file path"),
):
    """Export run results to a CSV file."""
    _client().download(f"/api/runs/{run_id}/export", output_path=output)
    console.print(f"[green]Exported results to {output}[/green]")
