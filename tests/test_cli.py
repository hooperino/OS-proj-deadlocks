import json

from deadlock_sim.cli.main import main


def test_single_run_cli_end_to_end(capsys):
    rc = main(["single-run", "--condition", "heavy", "--seed", "101", "--strategy", "prevention"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "status=COMPLETE" in out
    assert "condition=heavy seed=101 strategy=prevention" in out


def test_single_run_cli_creates_missing_parent_directories_for_output(tmp_path):
    # Regression test: --output used to crash with FileNotFoundError if its
    # parent directory did not already exist.
    out_path = tmp_path / "nested" / "does" / "not" / "exist" / "result.json"
    rc = main(["single-run", "--condition", "light", "--seed", "1", "--strategy", "avoidance", "--output", str(out_path)])
    assert rc == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["condition"] == "light"
    assert data["seed"] == 1
    assert data["strategy"] == "avoidance"


def test_single_run_cli_warns_on_out_of_range_seed(capsys):
    rc = main(["single-run", "--condition", "light", "--seed", "999", "--strategy", "prevention"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "outside the documented" in err


def test_experiment_cli_quiet_suppresses_progress_but_not_final_summary(tmp_path, capsys):
    rc = main(["experiment", "--output", str(tmp_path), "--quiet"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "runs complete" not in out  # progress lines suppressed
    assert "Experiment complete." in out  # final confirmation still shown
    dirs = list(tmp_path.glob("experiment_*"))
    assert len(dirs) == 1
    assert (dirs[0] / "aggregate.csv").exists()
