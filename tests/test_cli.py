import json
import subprocess
import sys

from changeorder.cli import batch, main


def test_real_module_and_entrypoint(documents, tmp_path):
    output = tmp_path / "result.json"
    command = [
        sys.executable,
        "-m",
        "changeorder.cli",
        "extract",
        "--input",
        str(documents / "03_digital.pdf"),
        "--output",
        str(output),
        "--ocr",
        "off",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert (
        json.loads(output.read_text(encoding="utf-8"))["data"]["change_order_number"]["value"]
        == "CO-003"
    )
    assert not completed.stdout


def test_stdout_and_partial_failed_exit_codes(capsys):
    assert main(["extract", "--text", "CHANGE ORDER\nCO Number: 2"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "partial"
    assert main(["extract", "--text", ""]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_batch_independence_unsupported_and_same_stem(tmp_path, offline):
    inputs, outputs = tmp_path / "inputs", tmp_path / "outputs"
    inputs.mkdir()
    (inputs / "good.txt").write_text(
        "CHANGE ORDER\nCO Number: 1\nProject: A\nTotal Change Amount: 100", encoding="utf-8"
    )
    (inputs / "good.pdf").write_bytes(b"bad pdf")
    (inputs / "unsupported.csv").write_text("anything", encoding="utf-8")
    results = batch(inputs, outputs, offline)
    assert sorted(result.status for result in results) == ["failed", "failed", "success"]
    assert (outputs / "good.txt.json").is_file()
    assert (outputs / "good.pdf.json").is_file()
    assert json.loads((outputs / "batch-summary.json").read_text())["counts"]["success"] == 1
    assert main(["batch", "--input-dir", str(inputs), "--output-dir", str(outputs)]) == 1


def test_cannot_overwrite_source(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("CHANGE ORDER", encoding="utf-8")
    assert main(["extract", "--input", str(source), "--output", str(source)]) == 1
    assert source.read_text() == "CHANGE ORDER"


def test_stdin_multiline():
    completed = subprocess.run(
        [sys.executable, "-m", "changeorder", "extract", "--stdin"],
        input="CHANGE ORDER\nCO Number: 0002\nProject: A\nTotal Change Amount: USD 10",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["data"]["change_order_number"]["value"] == "0002"
