"""Adopt an unmounted Keycloak database into an empty Compose-owned volume.

The stopped legacy container remains recoverable. A private host backup is kept
on success and failure; neither containers nor volumes are removed by this script.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DATA_PATH = "/opt/keycloak/data"
_PROJECT = "com.docker.compose.project"
_SERVICE = "com.docker.compose.service"
_UI_SERVICES = {"open-webui", "chainlit"}
_EMPTY = 'contents="$(ls -A /target)" || exit 43; [ -z "$contents" ] || exit 42'
_COPY = _EMPTY + "; cp -a /backup/. /target/; chown -R 1000:0 /target"


class MigrationError(RuntimeError):
    """A safe automatic adoption was not possible; source data is retained."""


@dataclass(frozen=True)
class Adoption:
    volume: str
    backup: Path


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    # The caller constructs Docker argv and validates project, image, volume and IDs.
    return subprocess.run(  # nosec B603
        args, capture_output=True, text=True, check=False, timeout=180
    )


def _checked(runner: Callable, args: list[str]) -> subprocess.CompletedProcess[str]:
    result = runner(args)
    if result.returncode:
        # Docker stdout/stderr may contain private paths or configuration values.
        raise MigrationError(f"Docker {args[1]} failed (exit {result.returncode})")
    return result


def _helper(image: str, volume: str, *, backup: Path | None = None) -> list[str]:
    mount = f"type=volume,src={volume},dst=/target,volume-nocopy"
    args = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "0",
        "--entrypoint",
        "/bin/sh",
        "--mount",
        mount + (",readonly" if backup is None else ""),
    ]
    if backup is not None:
        args.extend(["--mount", f"type=bind,src={backup},dst=/backup,readonly"])
    args.extend([image, "-eu", "-c", _EMPTY if backup is None else _COPY])
    return args


def preserve_keycloak_data(
    compose: Path,
    env_file: Path,
    *,
    runner: Callable = run,
) -> Adoption | None:
    command = [
        "docker",
        "compose",
        "-f",
        str(compose.resolve()),
        "--env-file",
        str(env_file.resolve()),
    ]
    ids = _checked(runner, [*command, "ps", "--all", "--quiet", "keycloak"]).stdout.split()
    if not ids:
        return None
    if len(ids) != 1:
        raise MigrationError("Expected exactly one legacy Keycloak container")
    source = json.loads(_checked(runner, ["docker", "inspect", ids[0]]).stdout)[0]
    config = json.loads(_checked(runner, [*command, "config", "--format", "json"]).stdout)
    project = config.get("name", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise MigrationError("Cannot establish the Compose project identity")
    labels = source.get("Config", {}).get("Labels") or {}
    if labels.get(_PROJECT) != project or labels.get(_SERVICE) != "keycloak":
        raise MigrationError("Keycloak container does not belong to the requested project")
    service = config["services"]["keycloak"]
    target = next(
        (item for item in service.get("volumes", []) if item.get("target") == DATA_PATH), None
    )
    if not target or target.get("type") != "volume":
        raise MigrationError("Compose must mount a named volume at /opt/keycloak/data")
    alias = target["source"]
    definition = config.get("volumes", {}).get(alias, {})
    volume = definition.get("name") or f"{project}_{alias}"
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", volume):
        raise MigrationError("Invalid Keycloak volume name")
    current_mount = next(
        (mount for mount in source.get("Mounts", []) if mount.get("Destination") == DATA_PATH),
        None,
    )
    if current_mount is not None:
        if current_mount.get("Type") != "volume" or current_mount.get("Name") != volume:
            raise MigrationError(
                "Existing Keycloak data mount differs from the configured named volume; "
                "no data was changed"
            )
        return None
    image = service.get("image", "")
    if not re.fullmatch(r"(?:quay\.io/)?keycloak/keycloak(?::[\w.-]+|@sha256:[a-f0-9]{64})", image):
        raise MigrationError("Volume adoption requires the configured official Keycloak image")

    inspected = runner(["docker", "volume", "inspect", volume])
    if inspected.returncode:
        if "no such volume" not in inspected.stderr.lower():
            raise MigrationError("Cannot inspect the Keycloak target volume")
        _checked(
            runner,
            [
                "docker",
                "volume",
                "create",
                "--label",
                f"{_PROJECT}={project}",
                "--label",
                f"com.docker.compose.volume={alias}",
                volume,
            ],
        )
    else:
        owner = (json.loads(inspected.stdout)[0].get("Labels") or {}).get(_PROJECT)
        if owner and owner != project:
            raise MigrationError("Keycloak target volume belongs to another project")
    empty = runner(_helper(image, volume))
    if empty.returncode == 42:
        raise MigrationError("Keycloak target volume is not empty; no data was overwritten")
    if empty.returncode:
        raise MigrationError("Cannot verify that the Keycloak target volume is empty")

    project_ids = _checked(
        runner, ["docker", "ps", "--all", "--quiet", "--filter", f"label={_PROJECT}={project}"]
    ).stdout.split()
    containers = (
        json.loads(_checked(runner, ["docker", "inspect", *project_ids]).stdout)
        if project_ids
        else []
    )
    owned_ui = []
    for item in containers:
        item_labels = item.get("Config", {}).get("Labels") or {}
        if (
            item_labels.get(_PROJECT) == project
            and item_labels.get(_SERVICE) in _UI_SERVICES
            and item.get("State", {}).get("Running")
        ):
            owned_ui.append(item["Id"])
    keycloak_id = source["Id"]
    running_keycloak = bool(source.get("State", {}).get("Running"))
    originally_running = ([keycloak_id] if running_keycloak else []) + owned_ui
    backup = Path(tempfile.mkdtemp(prefix="knowledge-keycloak-backup-"))
    data_backup = backup / "data"
    data_backup.mkdir(mode=0o700)
    try:
        # Freeze UI requests before taking the embedded database offline.
        if owned_ui:
            _checked(runner, ["docker", "stop", "--time", "60", *owned_ui])
        if running_keycloak:
            _checked(runner, ["docker", "stop", "--time", "60", keycloak_id])
        _checked(runner, ["docker", "cp", f"{keycloak_id}:{DATA_PATH}/.", str(data_backup)])
        # Recheck emptiness immediately before copying into the target volume.
        _checked(runner, _helper(image, volume, backup=data_backup))
    except BaseException as error:
        failed_restarts = []
        for container_id in originally_running:
            try:
                _checked(runner, ["docker", "start", container_id])
            except (MigrationError, OSError, subprocess.SubprocessError):
                failed_restarts.append(container_id)
        detail = "; some original services could not be restarted" if failed_restarts else ""
        raise MigrationError(
            f"Keycloak adoption failed{detail}. Backup retained at: {backup}"
        ) from error
    return Adoption(volume=volume, backup=backup)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", type=Path, default=root / "infra/app/compose.yml")
    parser.add_argument("--env-file", type=Path, default=root / ".env")
    args = parser.parse_args()
    try:
        adopted = preserve_keycloak_data(args.compose, args.env_file)
    except MigrationError as error:
        raise SystemExit(str(error)) from None
    if adopted:
        print(f"Keycloak data preserved in {adopted.volume}. Backup retained at: {adopted.backup}")
    else:
        print("Keycloak data adoption is not needed")


if __name__ == "__main__":
    main()
