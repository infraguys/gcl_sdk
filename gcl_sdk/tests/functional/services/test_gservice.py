#    Copyright 2025 Genesis Corporation.
#
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import sys
import types
from pathlib import Path
import textwrap

import pytest

from oslo_config import cfg

from gcl_sdk.common.services import gservice as gservice_mod
from gcl_sdk.cmd import gservice as gservice_cmd


class DummySvc:
    def __init__(self):
        self.setup_called = 0
        self.iter_called = 0

    def _setup(self):
        self.setup_called += 1

    def _loop_iteration(self):
        self.iter_called += 1


def write_ini(path: Path, content: str):
    # Normalize indentation per line to avoid oslo.config continuation parsing
    text = textwrap.dedent(content)
    lines = [ln.lstrip() for ln in text.splitlines()]
    # Drop leading/trailing blank lines, keep internal blanks
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    path.write_text("\n".join(lines) + "\n")


def reset_oslo_singletons():
    # Reset the global oslo.config singleton to avoid cross-test pollution
    cfg.CONF.reset()


class TestGService:
    def test_setup_delegates_to_all_services(self):
        s1, s2 = DummySvc(), DummySvc()
        svc = gservice_mod.GService(
            services=[s1, s2], iter_min_period=0.1, iter_pause=0.01
        )

        # Call protected method intentionally to test delegation
        svc._setup()

        assert s1.setup_called == 1
        assert s2.setup_called == 1

    def test_iteration_delegates_to_all_services(self):
        s1, s2 = DummySvc(), DummySvc()
        svc = gservice_mod.GService(services=[s1, s2])

        # One iteration should call _loop_iteration once on each
        svc._iteration()

        assert s1.iter_called == 1
        assert s2.iter_called == 1


class TestLoadConfig:
    def test_load_config_requires_config_file(self, tmp_path: Path):
        reset_oslo_singletons()
        with pytest.raises(FileNotFoundError):
            gservice_cmd.load_config([], conf=cfg.ConfigOpts())

    def test_load_config_with_config_file(self, tmp_path: Path):
        reset_oslo_singletons()
        cfg_file = tmp_path / "gservice.ini"
        write_ini(cfg_file, "\n")

        conf = gservice_cmd.load_config(
            ["--config-file", str(cfg_file)], conf=cfg.ConfigOpts()
        )
        assert conf.config_file == [str(cfg_file)]


class TestMain:
    def _patch_logging_and_start(self, monkeypatch):
        # No-op logging configure
        monkeypatch.setattr(
            "gcl_sdk.common.log.configure", lambda: None, raising=True
        )
        # Prevent DB engine configuration from trying to connect anywhere
        try:
            monkeypatch.setattr(
                "restalchemy.storage.sql.engines.engine_factory.configure_postgresql_factory",
                lambda conf: None,
                raising=True,
            )
        except Exception:
            pass
        # Prevent real service loop
        started = {"called": False}

        def fake_start(self):
            started["called"] = True

        monkeypatch.setattr(
            gservice_mod.GService, "start", fake_start, raising=True
        )
        return started

    def test_main_loads_services_via_cfg_load_class(
        self, tmp_path: Path, monkeypatch
    ):
        reset_oslo_singletons()
        started = self._patch_logging_and_start(monkeypatch)

        # Create a fake service class
        class MySvc:
            @staticmethod
            def get_svc_config_opts():
                # Return empty opts to avoid entering options-building path
                return {}

            def __init__(self, value: int = 42):
                self.value = value

            @classmethod
            def from_config(cls, path):
                return cls(value=7)

        # Patch class loader
        loaded_names = []

        def fake_cfg_load(name):
            loaded_names.append(name)
            return MySvc

        monkeypatch.setattr(
            "gcl_sdk.agents.universal.utils.cfg_load_class",
            fake_cfg_load,
            raising=True,
        )

        # Build config file for two services of the same class with different values
        cfg_file = tmp_path / "gservice.ini"
        write_ini(
            cfg_file,
            """
            [gservice]
            services = MySvc
            iter_min_period = 5
            iter_pause = 0.5
            disable_auto_opts = MySvc
            """.strip(),
        )

        # Simulate load_config returning a minimal configuration object
        class FakeSection(dict):
            pass

        class FakeConf(dict):
            def __init__(self):
                super().__init__()
                self.config_file = str(cfg_file)
                self["gservice"] = FakeSection(
                    services=["MySvc"],
                    disable_auto_opts=["MySvc"],
                    iter_min_period=5,
                    iter_pause=0.5,
                )

            def __contains__(self, key):
                return False

        monkeypatch.setattr(
            gservice_cmd,
            "load_config",
            lambda args, conf=None: FakeConf(),
            raising=True,
        )

        # Spy on GService __init__ to check parameters and captured services list
        init_args = {}
        real_init = gservice_mod.GService.__init__

        def spy_init(self, services, iter_min_period, iter_pause):
            init_args["services"] = services
            init_args["iter_min_period"] = iter_min_period
            init_args["iter_pause"] = iter_pause
            real_init(
                self,
                services=services,
                iter_min_period=iter_min_period,
                iter_pause=iter_pause,
            )

        monkeypatch.setattr(
            gservice_mod.GService, "__init__", spy_init, raising=True
        )

        gservice_cmd.main()

        assert started["called"] is True
        assert loaded_names == ["MySvc"]
        assert isinstance(init_args.get("services")[0], MySvc)
        assert init_args.get("iter_min_period") == 5
        assert init_args.get("iter_pause") == 0.5

    def test_main_disable_auto_opts_uses_from_config(
        self, tmp_path: Path, monkeypatch
    ):
        reset_oslo_singletons()
        started = self._patch_logging_and_start(monkeypatch)

        cfg_file = tmp_path / "gservice.ini"

        class AutoSvc:
            @staticmethod
            def get_svc_config_opts():
                # Would be ignored due to disable_auto_opts
                return {"autosvc": [cfg.StrOpt("foo", default="bar")]}

            @classmethod
            def from_config(cls, path):
                assert path == str(cfg_file)
                inst = cls()
                inst.loaded_via = "from_config"
                return inst

            def __init__(self):
                self.loaded_via = "ctor"

        # Any name, we'll make cfg_load_class return AutoSvc
        monkeypatch.setattr(
            "gcl_sdk.agents.universal.utils.cfg_load_class",
            lambda name: AutoSvc,
            raising=True,
        )

        write_ini(
            cfg_file,
            """
            [gservice]
            services = AutoSvc
            disable_auto_opts = AutoSvc
            """.strip(),
        )

        class FakeSection(dict):
            pass

        class FakeConf(dict):
            def __init__(self):
                super().__init__()
                self.config_file = str(cfg_file)
                self["gservice"] = FakeSection(
                    services=["AutoSvc"],
                    disable_auto_opts=["AutoSvc"],
                    iter_min_period=3,
                    iter_pause=0.1,
                )

            def __contains__(self, key):
                return False

        monkeypatch.setattr(
            gservice_cmd,
            "load_config",
            lambda args, conf=None: FakeConf(),
            raising=True,
        )

        constructed = {}

        def spy_init(self, services, iter_min_period, iter_pause):
            constructed["services"] = services
            # Do not call the real initializer to avoid starting timers/loops
            return None

        monkeypatch.setattr(
            gservice_mod.GService, "__init__", spy_init, raising=True
        )

        gservice_cmd.main()

        assert started["called"] is True
        assert constructed["services"], "services were not passed to GService"
        assert (
            getattr(constructed["services"][0], "loaded_via", None)
            == "from_config"
        )

    def test_main_loads_service_from_entry_point_on_valueerror(
        self, tmp_path: Path, monkeypatch
    ):
        reset_oslo_singletons()
        started = self._patch_logging_and_start(monkeypatch)

        class EPSvc:
            @staticmethod
            def get_svc_config_opts():
                return {}

            def __init__(self, enabled: bool = True):
                self.enabled = enabled

            @classmethod
            def from_config(cls, path):
                return cls(enabled=False)

        # First, make cfg_load_class raise ValueError so entry point path is used
        def raise_value_error(name):
            raise ValueError("not a module path")

        monkeypatch.setattr(
            "gcl_sdk.agents.universal.utils.cfg_load_class",
            raise_value_error,
            raising=True,
        )
        loaded_ep = {}
        monkeypatch.setattr(
            "gcl_sdk.common.utils.load_from_entry_point",
            lambda group, name: EPSvc if group else None,
            raising=True,
        )

        cfg_file = tmp_path / "gservice.ini"
        write_ini(
            cfg_file,
            """
            [gservice]
            services = EPSvc
            disable_auto_opts = EPSvc
            """.strip(),
        )

        class FakeSection(dict):
            pass

        class FakeConf(dict):
            def __init__(self):
                super().__init__()
                self.config_file = str(cfg_file)
                self["gservice"] = FakeSection(
                    services=["EPSvc"],
                    disable_auto_opts=["EPSvc"],
                    iter_min_period=3,
                    iter_pause=0.1,
                )

            def __contains__(self, key):
                return False

        monkeypatch.setattr(
            gservice_cmd,
            "load_config",
            lambda args, conf=None: FakeConf(),
            raising=True,
        )
        gservice_cmd.main()
        assert started["called"] is True

    def test_main_configures_db_engine_when_db_section_present(
        self, tmp_path: Path, monkeypatch
    ):
        reset_oslo_singletons()
        started = self._patch_logging_and_start(monkeypatch)

        # Minimal service to allow the flow
        class Svc:
            @staticmethod
            def get_svc_config_opts():
                return {}

            def __init__(self, x: str = "y"):
                pass

            @classmethod
            def from_config(cls, path):
                return cls(x="z")

        monkeypatch.setattr(
            "gcl_sdk.agents.universal.utils.cfg_load_class",
            lambda name: Svc,
            raising=True,
        )

        db_called = {"called": False}

        def fake_cfg_db(conf):
            db_called["called"] = True

        monkeypatch.setattr(
            "restalchemy.storage.sql.engines.engine_factory.configure_postgresql_factory",
            fake_cfg_db,
            raising=True,
        )

        # Compose config with database section and service section
        cfg_file = tmp_path / "gservice.ini"
        write_ini(
            cfg_file,
            """
            [DEFAULT]
            use_syslog = false

            [gservice]
            services = Svc
            disable_auto_opts = Svc

            [database]
            connection = postgresql://user:pass@localhost:5432/db
            """.strip(),
        )

        class FakeSection(dict):
            pass

        class FakeConf(dict):
            def __init__(self):
                super().__init__()
                self.config_file = str(cfg_file)
                self["gservice"] = FakeSection(
                    services=["Svc"],
                    disable_auto_opts=["Svc"],
                    iter_min_period=3,
                    iter_pause=0.1,
                )

            def __contains__(self, key):
                return key == "database"

        monkeypatch.setattr(
            gservice_cmd,
            "load_config",
            lambda args, conf=None: FakeConf(),
            raising=True,
        )
        gservice_cmd.main()
        assert db_called["called"] is True
        assert started["called"] is True
