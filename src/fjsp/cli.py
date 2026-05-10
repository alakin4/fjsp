"""Click-based CLI for the FJSP solver and instance generator."""

from pathlib import Path

import click

from .input.generator import random_instance, toy_instance
from .input.io import load_instance, save_instance
from .output.gantt import plot_gantt
from .output.web_export import export_web_data
from .solver import grasp, total_makespan


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """FJSP solver and instance generator.

    Run `fjsp solve` to optimize an instance and `fjsp generate` to write a
    new instance file. With no subcommand, defaults to solving the bundled
    toy instance (`instances/toy.json` or the in-memory toy).
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(solve)


# ------------------------------- solve -----------------------------------

@cli.command()
@click.option(
    "--instance", "-i", "instance_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default="instances/toy.json",
    show_default=True,
    help="Path to the instance JSON. If missing, the bundled toy is used.",
)
@click.option("--max-iter", default=200, show_default=True, type=int)
@click.option("--alpha", default=0.3, show_default=True, type=float,
              help="GRASP RCL parameter; 0=greedy, 1=random.")
@click.option("--seed", default=0, show_default=True, type=int)
@click.option("--gantt", default="gantt.png", show_default=True,
              type=click.Path(dir_okay=False, path_type=Path),
              help="Where to save the static matplotlib Gantt.")
@click.option("--web-data", default="web/data.js", show_default=True,
              type=click.Path(dir_okay=False, path_type=Path),
              help="Where to save data for the React viewer.")
def solve(
    instance_path: Path,
    max_iter: int,
    alpha: float,
    seed: int,
    gantt: Path,
    web_data: Path,
) -> None:
    """Solve an FJSP instance with GRASP."""
    if instance_path.exists():
        instance = load_instance(instance_path)
        click.echo(f"Loaded instance '{instance.name}' from {instance_path}")
    else:
        instance = toy_instance()
        click.echo(f"No file at {instance_path}; using built-in toy instance.")

    click.echo(
        f"  products={instance.n_products}  machines={instance.n_machines}  "
        f"operators={instance.n_operators}  orders={instance.n_jobs}"
    )

    sched = grasp(instance, max_iter=max_iter, alpha=alpha, seed=seed)
    cmax = total_makespan(instance, sched)
    click.secho(f"Cmax = {cmax}", fg="green", bold=True)
    if cmax != sched.makespan:
        click.echo(f"  (solver-only span: {sched.makespan}; "
                   f"running ops extend Cmax to {cmax})")

    click.echo(
        f"  {'op':<14} {'mach':<5} {'op#':<5} {'setup':<6} "
        f"{'proc_start':<11} {'end':<5}"
    )
    for s in sched.ops:
        click.echo(
            f"  {repr(s.op):<14} M{s.machine:<4} "
            f"Op{s.operator:<3} {s.setup_duration:<6} "
            f"{s.proc_start:<11} {s.end:<5}"
        )

    plot_gantt(sched, instance, save_path=str(gantt))
    export_web_data(instance, sched, web_data)
    click.echo(f"Static Gantt:        {gantt}")
    click.echo(f"Interactive viewer:  open web/index.html  (data: {web_data})")


# ------------------------------ generate ---------------------------------

@cli.command()
@click.option("--name", default="rand", show_default=True,
              help="Instance name written to the JSON file.")
@click.option("--products", default=4, show_default=True, type=int)
@click.option("--machines", default=5, show_default=True, type=int)
@click.option("--operators", default=4, show_default=True, type=int)
@click.option("--orders", default=10, show_default=True, type=int)
@click.option("--horizon", default=200, show_default=True, type=int)
@click.option("--seed", default=0, show_default=True, type=int)
@click.option("--setup-fraction", default=0.5, show_default=True, type=float,
              help="Fraction of machines that require setup.")
@click.option("--operator-coverage", default=0.7, show_default=True, type=float,
              help="P(operator can run a given machine).")
@click.option("--output", "-o", "output_path", required=True,
              type=click.Path(dir_okay=False, path_type=Path),
              help="Where to write the instance JSON.")
def generate(
    name: str,
    products: int,
    machines: int,
    operators: int,
    orders: int,
    horizon: int,
    seed: int,
    setup_fraction: float,
    operator_coverage: float,
    output_path: Path,
) -> None:
    """Generate a synthetic FJSP instance and save it as JSON."""
    inst = random_instance(
        name=name,
        n_products=products,
        n_machines=machines,
        n_operators=operators,
        n_orders=orders,
        horizon=horizon,
        setup_machines_fraction=setup_fraction,
        operator_machine_coverage=operator_coverage,
        seed=seed,
    )
    written = save_instance(inst, output_path)
    click.secho(f"Wrote {written}", fg="green")
    click.echo(
        f"  products={inst.n_products}  machines={inst.n_machines}  "
        f"operators={inst.n_operators}  orders={inst.n_jobs}  "
        f"horizon={inst.horizon}"
    )


# ------------------------------ inspect ---------------------------------

@cli.command()
@click.argument("instance_path",
                type=click.Path(exists=True, dir_okay=False, path_type=Path))
def inspect(instance_path: Path) -> None:
    """Print a human-readable summary of an instance JSON file."""
    inst = load_instance(instance_path)
    click.secho(f"Instance: {inst.name}", bold=True)
    click.echo(f"  horizon: {inst.horizon}")
    click.echo(f"  products  ({inst.n_products}):")
    for p in inst.products:
        click.echo(f"    P{p.product_id} {p.name}: "
                   f"{p.n_stages} stages, "
                   f"machines per stage: "
                   f"{[len(s.eligible_machines) for s in p.stages]}")
    click.echo(f"  machines  ({inst.n_machines}):")
    for m in inst.machines:
        setup = "with setup" if m.setup_times else "no setup"
        click.echo(f"    M{m.machine_id} {m.name}: "
                   f"{len(m.availability)} window(s), {setup}, "
                   f"current_product={m.current_product_id}")
    click.echo(f"  operators ({inst.n_operators}):")
    for o in inst.operators:
        click.echo(f"    Op{o.operator_id} {o.name}: "
                   f"runs {sorted(o.eligible_machines)}, "
                   f"{len(o.shifts)} shift(s)")
    click.echo(f"  orders    ({inst.n_jobs}):")
    for o in inst.orders:
        n_stages = inst.product(o.product_id).n_stages
        completed = sorted(o.status.completed_stage_indices)
        running = sorted(o.status.running_stage_indices)
        pending = sorted(o.pending_stage_indices(n_stages))
        click.echo(f"    J{o.job_id} → P{o.product_id}, deadline={o.deadline}")
        click.echo(f"        completed: {completed or '[]'}")
        click.echo(f"        running:   {running or '[]'}")
        click.echo(f"        pending:   {pending or '[]'}")


if __name__ == "__main__":
    cli()
