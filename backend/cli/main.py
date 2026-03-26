"""AgenticEval CLI entry point."""
import typer

app = typer.Typer(
    name="agenticeval",
    help="AgenticEval — CLI for managing eval datasets, scorers, adapters, and runs.",
    no_args_is_help=True,
)

state = {"base_url": "http://localhost:8000"}


@app.callback()
def main(base_url: str = typer.Option("http://localhost:8000", "--base-url", "-u",
                                       help="Backend server URL")):
    """AgenticEval CLI."""
    state["base_url"] = base_url


from cli.datasets import datasets_app
app.add_typer(datasets_app, name="datasets")

from cli.scorers import scorers_app
app.add_typer(scorers_app, name="scorers")
