from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from operational_variance_toolkit.console.output import terminal_text
from operational_variance_toolkit.errors import (
    OutputExistsError,
    PublicationError,
    PublicationOwnershipError,
)
from operational_variance_toolkit.storage import _windows_publication as native
from operational_variance_toolkit.storage.publication import publish_new


def _verify_file(path):
    assert path.read_text() == "complete"


def test_unqualified_platform_rejects_before_any_mutation(tmp_path, monkeypatch):
    before = list(tmp_path.iterdir())
    monkeypatch.setattr(native.sys, "platform", "linux")
    with pytest.raises(PublicationError, match="G1-P"):
        with publish_new(tmp_path / "result"):
            pytest.fail("Unqualified platform was enabled")
    assert list(tmp_path.iterdir()) == before


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows qualification only")
class TestWindowsPublication:
    def test_native_x64_cpython_probe_and_publication(self, tmp_path, record_testsuite_property):
        machines = native._machine_types()
        record_testsuite_property(
            "native-process-qualification",
            json.dumps({"implementation": sys.implementation.name, "machines": machines}),
        )
        assert sys.implementation.name == "cpython"
        assert machines == (0, 0x8664)
        final = tmp_path / "result"
        with publish_new(final) as publication:
            publication.staged_path.write_text("complete")
            publication.commit(verify=_verify_file)
        assert final.read_text() == "complete"
        assert not list(tmp_path.glob(".ovtk-stage-*"))

    def test_substituted_native_unknown_amd64_is_accepted(self, tmp_path, monkeypatch):
        # Decision-logic control only; this does not qualify another machine.
        self._substitute_machine_probe(monkeypatch, (0, 0x8664))
        final = tmp_path / "result"
        with publish_new(final) as publication:
            publication.staged_path.write_text("complete")
            publication.commit(verify=_verify_file)
        assert final.read_text() == "complete"

    @staticmethod
    def _substitute_machine_probe(monkeypatch, machines, *, success=True):
        kernel = native._kernel()

        class SubstitutedMachineProbe:
            def __getattr__(self, name):
                return getattr(kernel, name)

            def IsWow64Process2(self, handle, process, host):
                assert handle == kernel.GetCurrentProcess()
                if machines is not None:
                    ctypes.cast(process, ctypes.POINTER(ctypes.c_ushort)).contents.value = machines[
                        0
                    ]
                    ctypes.cast(host, ctypes.POINTER(ctypes.c_ushort)).contents.value = machines[1]
                ctypes.set_last_error(0 if success else 87)
                return success

        monkeypatch.setattr(native, "_kernel", lambda: SubstitutedMachineProbe())

    @pytest.mark.parametrize(
        "machines",
        [
            pytest.param((0x014C, 0x8664), id="x86-process-on-amd64"),
            pytest.param((0, 0x014C), id="native-x86"),
            pytest.param((0, 0xAA64), id="native-arm64"),
            pytest.param((0xA641, 0xAA64), id="arm64ec"),
            pytest.param((0, 0xA641), id="native-arm64ec-code"),
            pytest.param((0x8664, 0xAA64), id="x64-emulation-on-arm64"),
            pytest.param((0x014C, 0xAA64), id="x86-emulation-on-arm64"),
            pytest.param((0, 0), id="unknown-host"),
            pytest.param((0xFFFF, 0x8664), id="unknown-process"),
            pytest.param((0, 0xFFFF), id="unrecognized-host"),
            pytest.param((0x8664, 0x8664), id="inconsistent-amd64-emulation"),
            pytest.param((0xA641, 0x8664), id="arm64ec-process-on-amd64"),
        ],
    )
    def test_architecture_guard_rejects_before_staging(self, tmp_path, monkeypatch, machines):
        # Substituted API outputs cover rejection partitions, not native platforms.
        self._substitute_machine_probe(monkeypatch, machines)
        with pytest.raises(PublicationError, match="native AMD64/x64") as error:
            with publish_new(tmp_path / "result"):
                pytest.fail("Unqualified process reached staging")
        assert terminal_text(error.value) == str(error.value)
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("success", [False, True], ids=["failure", "unset-success"])
    def test_failed_or_unset_probe_rejects_before_staging(self, tmp_path, monkeypatch, success):
        self._substitute_machine_probe(monkeypatch, None, success=success)
        match = "Windows error 87" if not success else "native AMD64/x64"
        with pytest.raises(PublicationError, match=match) as error:
            with publish_new(tmp_path / "result"):
                pytest.fail("Indeterminate probe reached staging")
        assert str(error.value).isascii()
        assert not any(ord(char) < 32 or ord(char) == 127 for char in str(error.value))
        assert terminal_text(error.value) == str(error.value)
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("failure", [AttributeError("API missing"), OSError("probe failure")])
    def test_unavailable_probe_rejects_before_staging(self, tmp_path, monkeypatch, failure):
        def unavailable():
            raise failure

        monkeypatch.setattr(native, "_kernel", unavailable)
        with pytest.raises(PublicationError, match="probe is unavailable") as error:
            with publish_new(tmp_path / "result"):
                pytest.fail("Unavailable API reached staging")
        assert terminal_text(error.value) == str(error.value)
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("implementation", ["pypy", "unknown"])
    def test_non_cpython_rejects_before_native_probe(self, tmp_path, monkeypatch, implementation):
        monkeypatch.setattr(native.sys.implementation, "name", implementation)

        def forbidden():
            pytest.fail("Non-CPython reached the native probe")

        monkeypatch.setattr(native, "_kernel", forbidden)
        with pytest.raises(PublicationError, match="CPython 3.14") as error:
            with publish_new(tmp_path / "result"):
                pytest.fail("Non-CPython reached staging")
        assert terminal_text(error.value) == str(error.value)
        assert list(tmp_path.iterdir()) == []

    def test_long_unicode_paths_publish_on_qualified_volume(self, tmp_path):
        parent = tmp_path
        while len(str(parent)) < 280:
            parent = parent / "long-path-component"
            parent.mkdir()
        final = parent / "café-結果"
        with publish_new(final) as publication:
            publication.staged_path.write_text("complete")
            publication.commit(verify=_verify_file)
        assert final.read_text() == "complete"

    @pytest.mark.parametrize("kind", ["file", "directory"])
    def test_complete_payload_published_and_private_stage_cleaned(self, tmp_path, kind):
        final = tmp_path / "result"
        with publish_new(final) as publication:
            if kind == "file":
                publication.staged_path.write_text("complete")
                verify = _verify_file
            else:
                publication.staged_path.mkdir()
                (publication.staged_path / "manifest").write_text("complete")

                def verify(path):
                    assert (path / "manifest").read_text() == "complete"

            assert not final.exists()
            assert publication.commit(verify=verify) == final
        assert final.exists()
        assert not list(tmp_path.glob(".ovtk-stage-*"))
        with pytest.raises(PublicationOwnershipError, match="closed"):
            publication.commit(verify=verify)

    @pytest.mark.parametrize("kind", ["file", "empty", "nonempty"])
    def test_all_existing_names_are_collisions(self, tmp_path, kind):
        final = tmp_path / "result"
        if kind == "file":
            final.write_text("winner")
        else:
            final.mkdir()
            if kind == "nonempty":
                (final / "winner").write_text("winner")
        with pytest.raises(OutputExistsError):
            with publish_new(final):
                pytest.fail("Existing destination accepted")
        assert final.exists()
        assert not list(tmp_path.glob(".ovtk-stage-*"))

    def test_verifier_failure_cleans_only_owned_stage(self, tmp_path):
        final = tmp_path / "result"
        sentinel = tmp_path / "unrelated"
        sentinel.write_text("unchanged")

        def reject(_):
            raise ValueError("bad content")

        with pytest.raises(ValueError, match="bad content"):
            with publish_new(final) as publication:
                publication.staged_path.write_text("complete")
                publication.commit(verify=reject)
        assert not final.exists()
        assert sentinel.read_text() == "unchanged"
        assert not list(tmp_path.glob(".ovtk-stage-*"))

    def test_failure_after_commit_never_deletes_public_output(self, tmp_path):
        final = tmp_path / "result"
        with pytest.raises(RuntimeError):
            with publish_new(final) as publication:
                publication.staged_path.write_text("complete")
                publication.commit(verify=_verify_file)
                raise RuntimeError("later caller failure")
        assert final.read_text() == "complete"

    def test_race_after_verification_cannot_replace_winner(self, tmp_path):
        final = tmp_path / "result"
        with pytest.raises(OutputExistsError):
            with publish_new(final) as publication:
                publication.staged_path.write_text("complete")

                def competitor(_):
                    final.mkdir()
                    (final / "winner").write_text("winner")

                publication.commit(verify=competitor)
        assert (final / "winner").read_text() == "winner"

    def test_two_threads_have_exactly_one_winner(self, tmp_path):
        barrier = threading.Barrier(2)
        final = tmp_path / "result"

        def producer(value):
            try:
                with publish_new(final) as publication:
                    publication.staged_path.write_text(value)
                    barrier.wait(timeout=10)
                    publication.commit(verify=lambda path: None)
                return "winner"
            except OutputExistsError:
                return "collision"

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(producer, ["one", "two"]))
        assert sorted(results) == ["collision", "winner"]
        assert final.read_text() in {"one", "two"}
        assert not list(tmp_path.glob(".ovtk-stage-*"))

    def test_two_native_processes_have_exactly_one_winner(self, tmp_path):
        script = """
import json,sys,time
from pathlib import Path
from operational_variance_toolkit.storage.publication import publish_new
from operational_variance_toolkit.errors import OutputExistsError
root=Path(sys.argv[1]); token=sys.argv[2]
try:
    with publish_new(root/'result') as publication:
        publication.staged_path.write_text(token)
        (root/('ready'+token)).write_text('ready')
        deadline=time.monotonic()+15
        while not (root/'go').exists():
            if time.monotonic()>deadline: raise RuntimeError('barrier timeout')
            time.sleep(.01)
        publication.commit(verify=lambda path: None)
    print(json.dumps({'result':'winner'}))
except OutputExistsError:
    print(json.dumps({'result':'collision'}))
"""
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", script, str(tmp_path), value],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for value in ("one", "two")
        ]
        try:
            deadline = time.monotonic() + 15
            while not all((tmp_path / ("ready" + value)).exists() for value in ("one", "two")):
                assert time.monotonic() < deadline, "Producer readiness timed out"
                time.sleep(0.01)
            (tmp_path / "go").write_text("go")
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=20)
                assert process.returncode == 0, stderr
                results.append(json.loads(stdout)["result"])
            assert sorted(results) == ["collision", "winner"]
            assert (tmp_path / "result").read_text() in {"one", "two"}
            assert not list(tmp_path.glob(".ovtk-stage-*"))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_ownership_loss_retains_foreign_and_original_stage(self, tmp_path):
        moved = tmp_path / "original-stage"
        foreign = None
        with pytest.raises(PublicationOwnershipError, match="retained"):
            with publish_new(tmp_path / "result") as publication:
                stage = publication.staged_path.parent
                stage.rename(moved)
                stage.mkdir()
                foreign = stage / "foreign"
                foreign.write_text("foreign owner")
        assert foreign.read_text() == "foreign owner"
        assert moved.exists()
        assert not (tmp_path / "result").exists()

    def test_private_acl_excludes_general_users(self, tmp_path):
        with publish_new(tmp_path / "result") as publication:
            acl = subprocess.run(
                ["icacls", str(publication.staged_path.parent)],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            assert "BUILTIN\\Users:" not in acl
            assert "Everyone:" not in acl
            assert "Authenticated Users:" not in acl
            assert "Administrators:" in acl

    def test_junction_parent_rejected_before_mutation(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "redirect"
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, check=True
        )
        with pytest.raises(PublicationError, match="redirected"):
            with publish_new(link / "result"):
                pytest.fail("Junction parent accepted")
        assert list(target.iterdir()) == []

    def test_unsupported_filesystem_rejected_before_staging(self, tmp_path, monkeypatch):
        kernel = native._kernel()

        class UnsupportedFilesystem:
            def __getattr__(self, name):
                return getattr(kernel, name)

            def GetVolumeInformationW(self, *args):
                result = kernel.GetVolumeInformationW(*args)
                args[6].value = "ReFS"
                return result

        monkeypatch.setattr(native, "_kernel", lambda: UnsupportedFilesystem())
        with pytest.raises(PublicationError, match="NTFS"):
            with publish_new(tmp_path / "result"):
                pytest.fail("Unsupported filesystem accepted")
        assert list(tmp_path.iterdir()) == []

    def test_pair_order_and_orphan_retention(self, tmp_path, monkeypatch):
        final, sidecar = tmp_path / "database", tmp_path / "database.json"
        move = native.move_no_replace
        observed = []

        def racing_move(source, destination):
            observed.append(destination)
            if destination == final:
                assert sidecar.read_text() == "sidecar"
                final.write_text("competitor")
            move(source, destination)

        monkeypatch.setattr(native, "move_no_replace", racing_move)
        with pytest.raises(PublicationError, match="sidecar retained"):
            with publish_new(final) as publication:
                publication.staged_path.write_text("database")
                publication.staged_sidecar.write_text("sidecar")
                publication.commit_pair(sidecar, verify=lambda path: None)
        assert observed == [sidecar, final]
        assert sidecar.read_text() == "sidecar"
        assert final.read_text() == "competitor"

    @pytest.mark.parametrize("allow_delete", [False, True])
    def test_sharing_violation_is_controlled_and_does_not_publish(
        self, tmp_path, allow_delete, record_testsuite_property
    ):
        final = tmp_path / "result"
        with publish_new(final) as publication:
            publication.staged_path.write_text("complete")
            kernel = native._kernel()
            access, sharing = 0x80000000, 3 | (4 if allow_delete else 0)
            invalid = ctypes.c_void_p(-1).value
            ctypes.set_last_error(0)
            handle = kernel.CreateFileW(
                native._native(publication.staged_path), access, sharing, None, 3, 0, None
            )
            setup_error = ctypes.get_last_error()
            record = {
                "desired_access": access,
                "share_mode": sharing,
                "setup_error": setup_error,
                "valid_handle": handle not in (None, invalid),
            }
            record_testsuite_property(f"sharing-setup-{allow_delete}", json.dumps(record))
            assert handle not in (None, invalid), record
            try:
                # OPEN_EXISTING + DELETE desired access, no delete-on-close flag:
                # this proves the sharing precondition without mutating the file.
                ctypes.set_last_error(0)
                probe = kernel.CreateFileW(
                    native._native(publication.staged_path), 0x10000, 7, None, 3, 0, None
                )
                probe_error = ctypes.get_last_error()
                record.update(probe_valid=probe not in (None, invalid), probe_error=probe_error)
                record_testsuite_property(f"sharing-probe-{allow_delete}", json.dumps(record))
                if probe not in (None, invalid):
                    kernel.CloseHandle(probe)
                if allow_delete:
                    assert record["probe_valid"], record
                    publication.commit(verify=_verify_file)
                    assert final.read_text() == "complete"
                else:
                    assert not record["probe_valid"] and probe_error == 32, record
                    with pytest.raises(PublicationError, match="Windows error 32"):
                        publication.commit(verify=_verify_file)
                    assert not final.exists()
                    assert publication.staged_path.read_text() == "complete"
            finally:
                kernel.CloseHandle(handle)
            if not allow_delete:
                publication.commit(verify=_verify_file)
        assert final.read_text() == "complete"
        assert not list(tmp_path.glob(".ovtk-stage-*"))

    def test_case_collision_is_not_replaced(self, tmp_path):
        (tmp_path / "Result").write_text("winner")
        with pytest.raises(OutputExistsError):
            with publish_new(tmp_path / "result"):
                pytest.fail("Case collision accepted")
        assert (tmp_path / "Result").read_text() == "winner"
