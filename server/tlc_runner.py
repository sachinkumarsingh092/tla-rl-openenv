"""
TLC/SANY subprocess wrapper.

Writes TLA+ specs to temp files, runs Java-based TLA+ tools, parses output.
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

TLA2TOOLS_JAR = os.environ.get(
    "TLA2TOOLS_JAR", "/opt/tla2tools.jar"
)

JAVA_BIN = os.environ.get("JAVA_BIN", "java")

SANY_TIMEOUT = int(os.environ.get("SANY_TIMEOUT", "15"))
TLC_TIMEOUT = int(os.environ.get("TLC_TIMEOUT", "30"))


@dataclass
class SANYResult:
    success: bool
    errors: List[str] = field(default_factory=list)
    raw_output: str = ""


@dataclass
class TLCResult:
    success: bool
    invariant_violated: bool = False
    invariant_name: str = ""
    counterexample: str = ""
    states_found: int = 0
    distinct_states: int = 0
    errors: List[str] = field(default_factory=list)
    raw_output: str = ""


def _find_jar() -> str:
    for candidate in [TLA2TOOLS_JAR, "/opt/tla2tools.jar", "tla2tools.jar"]:
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        "tla2tools.jar not found. Set TLA2TOOLS_JAR env var."
    )


def run_sany(spec_text: str, module_name: str = "Spec") -> SANYResult:
    """Run SANY syntax checker on a TLA+ specification."""
    jar = _find_jar()

    with tempfile.TemporaryDirectory(prefix="tla_sany_") as tmpdir:
        spec_path = Path(tmpdir) / f"{module_name}.tla"
        spec_path.write_text(spec_text)

        try:
            result = subprocess.run(
                [JAVA_BIN, "-cp", jar, "tla2sany.SANY", str(spec_path)],
                capture_output=True,
                text=True,
                timeout=SANY_TIMEOUT,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return SANYResult(
                success=False,
                errors=["SANY timed out after {} seconds".format(SANY_TIMEOUT)],
            )
        except FileNotFoundError:
            return SANYResult(
                success=False,
                errors=["Java runtime not found. Install JRE."],
            )

        output = result.stdout + "\n" + result.stderr
        errors = _parse_sany_errors(output)

        return SANYResult(
            success=len(errors) == 0 and result.returncode == 0,
            errors=errors,
            raw_output=output.strip(),
        )


def run_tlc(
    spec_text: str,
    cfg_text: str,
    module_name: str = "Spec",
) -> TLCResult:
    """Run TLC model checker on a TLA+ specification with config."""
    jar = _find_jar()

    with tempfile.TemporaryDirectory(prefix="tla_tlc_") as tmpdir:
        spec_path = Path(tmpdir) / f"{module_name}.tla"
        cfg_path = Path(tmpdir) / f"{module_name}.cfg"
        spec_path.write_text(spec_text)
        cfg_path.write_text(cfg_text)

        try:
            result = subprocess.run(
                [
                    JAVA_BIN,
                    "-Xmx512m",
                    "-jar",
                    jar,
                    "-workers",
                    "1",
                    "-config",
                    str(cfg_path),
                    str(spec_path),
                ],
                capture_output=True,
                text=True,
                timeout=TLC_TIMEOUT,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return TLCResult(
                success=False,
                errors=["TLC timed out after {} seconds".format(TLC_TIMEOUT)],
            )
        except FileNotFoundError:
            return TLCResult(
                success=False,
                errors=["Java runtime not found. Install JRE."],
            )

        output = result.stdout + "\n" + result.stderr
        return _parse_tlc_output(output, result.returncode)


def run_tlc_with_aux_files(
    spec_text: str,
    cfg_text: str,
    module_name: str = "Spec",
    aux_files: Optional[dict] = None,
) -> TLCResult:
    """Run TLC with additional auxiliary TLA+ files in the same directory."""
    jar = _find_jar()

    with tempfile.TemporaryDirectory(prefix="tla_tlc_") as tmpdir:
        spec_path = Path(tmpdir) / f"{module_name}.tla"
        cfg_path = Path(tmpdir) / f"{module_name}.cfg"
        spec_path.write_text(spec_text)
        cfg_path.write_text(cfg_text)

        if aux_files:
            for fname, content in aux_files.items():
                (Path(tmpdir) / fname).write_text(content)

        try:
            result = subprocess.run(
                [
                    JAVA_BIN,
                    "-Xmx512m",
                    "-jar",
                    jar,
                    "-workers",
                    "1",
                    "-config",
                    str(cfg_path),
                    str(spec_path),
                ],
                capture_output=True,
                text=True,
                timeout=TLC_TIMEOUT,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return TLCResult(
                success=False,
                errors=["TLC timed out after {} seconds".format(TLC_TIMEOUT)],
            )
        except FileNotFoundError:
            return TLCResult(
                success=False,
                errors=["Java runtime not found. Install JRE."],
            )

        output = result.stdout + "\n" + result.stderr
        return _parse_tlc_output(output, result.returncode)


def _parse_sany_errors(output: str) -> List[str]:
    errors = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(
            kw in stripped.lower()
            for kw in ["error", "unknown operator", "unexpected", "was not found"]
        ):
            if "error" in stripped.lower() or "unexpected" in stripped.lower():
                errors.append(stripped)
    if "Parsing Error" in output or "Lexical error" in output:
        block = []
        capture = False
        for line in output.splitlines():
            if "error" in line.lower() or "Error" in line:
                capture = True
            if capture:
                block.append(line.strip())
            if capture and line.strip() == "":
                capture = False
        if block and not errors:
            errors = block[:5]
    if not errors and "*** Errors:" in output:
        errors.append("SANY reported errors (see raw output)")
    return errors


def _parse_tlc_output(output: str, returncode: int) -> TLCResult:
    result = TLCResult(success=False, raw_output=output.strip())

    states_match = re.search(r"(\d+) states generated.*?(\d+) distinct", output)
    if states_match:
        result.states_found = int(states_match.group(1))
        result.distinct_states = int(states_match.group(2))

    if "Model checking completed. No error has been found" in output:
        result.success = True
        return result

    inv_match = re.search(r"Invariant (\w+) is violated", output)
    if inv_match:
        result.invariant_violated = True
        result.invariant_name = inv_match.group(1)
        ce_start = output.find("Error: Invariant")
        if ce_start >= 0:
            result.counterexample = output[ce_start : ce_start + 500]

    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Error:") or stripped.startswith("TLC threw"):
            result.errors.append(stripped)

    if "Parsing Error" in output or "Lexical error" in output:
        result.errors.append("TLA+ specification has syntax errors")

    if not result.errors and not result.success and returncode != 0:
        result.errors.append("TLC exited with code {}".format(returncode))

    return result
