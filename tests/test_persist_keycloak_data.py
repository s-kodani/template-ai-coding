"""Protect the only copy of a legacy Keycloak database during volume adoption."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


class DockerState:
    def __init__(
        self,
        *,
        present=True,
        mounted=False,
        data_mount=None,
        volume_data=None,
        fail_copy=False,
        fail_volume_copy=False,
    ):
        self.present = present
        self.mounted = mounted
        self.data_mount = data_mount or {
            "Destination": "/opt/keycloak/data",
            "Type": "volume",
            "Name": "knowledge-app_keycloak_data",
        }
        if data_mount is not None:
            self.mounted = True
        self.volume_data = volume_data
        self.fail_copy = fail_copy
        self.fail_volume_copy = fail_volume_copy
        self.commands = []
        self.running = {"kc-owned": True, "ui-owned": True, "ui-other": True}
        self.labels = {
            "kc-owned": {
                "com.docker.compose.project": "knowledge-app",
                "com.docker.compose.service": "keycloak",
            },
            "ui-owned": {
                "com.docker.compose.project": "knowledge-app",
                "com.docker.compose.service": "open-webui",
            },
            "ui-other": {
                "com.docker.compose.project": "other-app",
                "com.docker.compose.service": "open-webui",
            },
        }

    def run(self, args):
        self.commands.append(args)
        output = ""
        code = 0
        if args[:2] == ["docker", "compose"]:
            if "ps" in args:
                output = "kc-owned\n" if self.present else ""
            elif "config" in args:
                output = json.dumps(
                    {
                        "name": "knowledge-app",
                        "services": {
                            "keycloak": {
                                "image": "keycloak/keycloak:26.6.4",
                                "volumes": [
                                    {
                                        "type": "volume",
                                        "source": "keycloak_data",
                                        "target": "/opt/keycloak/data",
                                    }
                                ],
                            }
                        },
                        "volumes": {"keycloak_data": {"name": "knowledge-app_keycloak_data"}},
                    }
                )
            else:
                raise AssertionError(args)
        elif args[:2] == ["docker", "inspect"]:
            output = json.dumps(
                [
                    {
                        "Id": item,
                        "Config": {"Labels": self.labels[item]},
                        "State": {"Running": self.running[item]},
                        "Mounts": [self.data_mount]
                        if item == "kc-owned" and self.mounted
                        else [],
                    }
                    for item in args[2:]
                ]
            )
        elif args[:2] == ["docker", "ps"]:
            # Docker's project-label filter scopes discovery; inspect still verifies labels.
            output = "kc-owned\nui-owned\nui-other\n"
        elif args[:3] == ["docker", "volume", "inspect"]:
            if self.volume_data is None:
                return subprocess.CompletedProcess(
                    args, 1, "", "Error response from daemon: get volume: no such volume"
                )
            output = json.dumps([{"Labels": {"com.docker.compose.project": "knowledge-app"}}])
        elif args[:3] == ["docker", "volume", "create"]:
            self.volume_data = {}
        elif args[:2] == ["docker", "stop"]:
            for item in args[4:]:
                self.running[item] = False
        elif args[:2] == ["docker", "start"]:
            for item in args[2:]:
                self.running[item] = True
        elif args[:2] == ["docker", "cp"]:
            assert not self.running["kc-owned"], "Backup must be taken after Keycloak stops"
            destination = Path(args[-1])
            destination.chmod(0o755)  # Docker may preserve source directory metadata.
            (destination / "h2").mkdir()
            (destination / "h2/keycloakdb.mv.db").write_bytes(b"original-user-sub-and-signing-keys")
            if self.fail_copy:
                raise RuntimeError("backup interrupted")
        elif args[:2] == ["docker", "run"]:
            if "/backup" in " ".join(args):
                assert self.volume_data == {}, "Never overwrite volume data"
                self.volume_data = {"h2/keycloakdb.mv.db": b"original-user-sub-and-signing-keys"}
                if self.fail_volume_copy:
                    self.volume_data = {"partial": b"retain-for-inspection"}
                    raise RuntimeError("copy failed")
            else:
                code = 0 if self.volume_data == {} else 42
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, output, "")


def test_missing_or_already_persistent_keycloak_is_noop(tmp_path):
    from scripts.persist_keycloak_data import preserve_keycloak_data

    for state in (DockerState(present=False), DockerState(mounted=True)):
        result = preserve_keycloak_data(
            tmp_path / "compose.yml", tmp_path / ".env", runner=state.run
        )
        assert result is None
        assert all(state.running.values())
        assert state.volume_data is None


def test_refuses_nonempty_target_before_stopping_anything(tmp_path):
    from scripts.persist_keycloak_data import MigrationError, preserve_keycloak_data

    state = DockerState(volume_data={"existing": b"do-not-touch"})
    with pytest.raises(MigrationError, match="not empty"):
        preserve_keycloak_data(tmp_path / "compose.yml", tmp_path / ".env", runner=state.run)
    assert all(state.running.values())
    assert state.volume_data == {"existing": b"do-not-touch"}
    assert not any(command[:2] == ["docker", "cp"] for command in state.commands)


@pytest.mark.parametrize(
    "data_mount",
    [
        {
            "Destination": "/opt/keycloak/data",
            "Type": "volume",
            "Name": "existing-keycloak-identities",
        },
        {
            "Destination": "/opt/keycloak/data",
            "Type": "bind",
            "Source": "/private/keycloak-identities",
        },
    ],
)
def test_refuses_a_different_existing_mount_without_mutating_storage(tmp_path, data_mount):
    from scripts.persist_keycloak_data import MigrationError, preserve_keycloak_data

    state = DockerState(data_mount=data_mount)
    with pytest.raises(MigrationError, match="data mount differs"):
        preserve_keycloak_data(tmp_path / "compose.yml", tmp_path / ".env", runner=state.run)
    assert all(state.running.values())
    assert state.volume_data is None
    assert not any(
        command[:2] in (["docker", "stop"], ["docker", "cp"], ["docker", "run"])
        or command[:3] == ["docker", "volume", "create"]
        for command in state.commands
    )


def test_copies_stopped_database_and_never_stops_another_project(tmp_path, monkeypatch):
    from scripts import persist_keycloak_data as migration

    backup = tmp_path / "private-backup"
    backup.mkdir(mode=0o700)
    monkeypatch.setattr(migration.tempfile, "mkdtemp", lambda **_: str(backup))
    state = DockerState()
    result = migration.preserve_keycloak_data(
        tmp_path / "compose.yml", tmp_path / ".env", runner=state.run
    )
    assert result.backup == backup
    assert backup.stat().st_mode & 0o777 == 0o700
    assert (
        backup / "data/h2/keycloakdb.mv.db"
    ).read_bytes() == b"original-user-sub-and-signing-keys"
    assert state.volume_data == {"h2/keycloakdb.mv.db": b"original-user-sub-and-signing-keys"}
    assert state.running == {"kc-owned": False, "ui-owned": False, "ui-other": True}
    assert not any(
        command[:2] == ["docker", "rm"] or command[:3] == ["docker", "volume", "rm"]
        for command in state.commands
    )


def test_backup_failure_restarts_owned_services_and_keeps_recovery_copy(tmp_path, monkeypatch):
    from scripts import persist_keycloak_data as migration

    backup = tmp_path / "private-backup"
    backup.mkdir(mode=0o700)
    monkeypatch.setattr(migration.tempfile, "mkdtemp", lambda **_: str(backup))
    state = DockerState(fail_copy=True)
    with pytest.raises(migration.MigrationError, match="Backup retained") as error:
        migration.preserve_keycloak_data(
            tmp_path / "compose.yml", tmp_path / ".env", runner=state.run
        )
    assert str(backup) in str(error.value)
    assert (backup / "data/h2/keycloakdb.mv.db").is_file()
    assert all(state.running.values())
    assert state.volume_data == {}


def test_refuses_a_source_from_another_compose_project(tmp_path):
    from scripts.persist_keycloak_data import MigrationError, preserve_keycloak_data

    state = DockerState()
    state.labels["kc-owned"]["com.docker.compose.project"] = "other-app"
    with pytest.raises(MigrationError, match="does not belong"):
        preserve_keycloak_data(tmp_path / "compose.yml", tmp_path / ".env", runner=state.run)
    assert all(state.running.values())
    assert state.volume_data is None


def test_failed_destination_copy_retains_both_backups_and_restarts_services(tmp_path, monkeypatch):
    from scripts import persist_keycloak_data as migration

    backup = tmp_path / "private-backup"
    backup.mkdir(mode=0o700)
    monkeypatch.setattr(migration.tempfile, "mkdtemp", lambda **_: str(backup))
    state = DockerState(fail_volume_copy=True)
    with pytest.raises(migration.MigrationError, match="Backup retained"):
        migration.preserve_keycloak_data(
            tmp_path / "compose.yml", tmp_path / ".env", runner=state.run
        )
    assert (
        backup / "data/h2/keycloakdb.mv.db"
    ).read_bytes() == b"original-user-sub-and-signing-keys"
    assert all(state.running.values())
    assert state.volume_data == {"partial": b"retain-for-inspection"}
