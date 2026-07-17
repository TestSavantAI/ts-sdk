import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
sys.modules.setdefault("requests", types.ModuleType("requests"))
fake_httpx = types.ModuleType("httpx")
fake_httpx.AsyncClient = object
fake_httpx.Client = object
sys.modules.setdefault("httpx", fake_httpx)

from testsavant.guard import OptunaOptimizer, build_discrete_configs


def test_build_discrete_configs_normalizes_preferences():
    configs, preferences = build_discrete_configs(
        {
            "threshold": [(0.1, 1.0), (0.2, 1.0)],
            "chunk_size": [(50, 0.0), (100, 1.0)],
        }
    )

    assert len(configs) == 4
    assert preferences == [0.0, 0.5, 0.0, 0.5]
    assert configs[0] == {"threshold": 0.1, "chunk_size": 50}
    assert configs[-1] == {"threshold": 0.2, "chunk_size": 100}


def test_optuna_optimizer_aggregates_duplicate_configs(monkeypatch):
    class DummyTrial:
        def __init__(self, number, params):
            self.number = number
            self._params = params
            self.user_attrs = {}

        def suggest_categorical(self, name, values):
            return self._params[name]

        def set_user_attr(self, key, value):
            self.user_attrs[key] = value

    class DummyStudy:
        def __init__(self):
            self.trials = []
            self.stop_called = False

        def stop(self):
            self.stop_called = True

        def optimize(self, objective, n_trials, callbacks):
            planned_params = [
                {"threshold": 0.25},
                {"threshold": 0.25},
                {"threshold": 0.5},
            ]
            for number, params in enumerate(planned_params[:n_trials]):
                trial = DummyTrial(number, params)
                objective(trial)
                self.trials.append(trial)
                for callback in callbacks:
                    callback(self, trial)
                if self.stop_called:
                    break

    class DummySamplers:
        class TPESampler:
            def __init__(self, seed):
                self.seed = seed

    class DummyLogging:
        WARNING = "warning"
        verbosity = "info"
        calls = []

        @classmethod
        def get_verbosity(cls):
            return cls.verbosity

        @classmethod
        def set_verbosity(cls, value):
            cls.calls.append(value)
            cls.verbosity = value

    class DummyOptunaModule:
        samplers = DummySamplers()
        logging = DummyLogging()

        @staticmethod
        def create_study(direction, sampler):
            return DummyStudy()

    monkeypatch.setattr("testsavant.guard.optimization.importlib.import_module", lambda name: DummyOptunaModule())

    optimizer = OptunaOptimizer(top_k=2, seed=1, exploration_ratio=0.2, min_exploration_trials=1)
    results = optimizer.optimize(
        search_space={"threshold": [(0.25, 0.0), (0.5, 1.0)]},
        score_fn=lambda config: 1.0 if config["threshold"] == 0.25 else 0.2,
        epochs=1,
        steps_per_epoch=3,
    )

    assert len(results) == 2
    assert results[0]["config"] == {"threshold": 0.25}
    assert results[0]["mean_score"] == 1.0
    assert any(result["num_evals"] == 2 for result in results)
    assert DummyLogging.calls == [DummyLogging.WARNING, "info"]


def test_optuna_optimizer_prefers_best_raw_score_when_scores_are_separated(monkeypatch):
    class DummyTrial:
        def __init__(self, number):
            self.number = number
            self.user_attrs = {}

        def suggest_categorical(self, name, values):
            return values[0]

        def set_user_attr(self, key, value):
            self.user_attrs[key] = value

    class DummyStudy:
        def __init__(self):
            self.trials = []

        def optimize(self, objective, n_trials, callbacks):
            for number in range(n_trials):
                trial = DummyTrial(number)
                objective(trial)
                self.trials.append(trial)
                for callback in callbacks:
                    callback(self, trial)

    class DummySamplers:
        class TPESampler:
            def __init__(self, seed, n_startup_trials=0):
                self.seed = seed
                self.n_startup_trials = n_startup_trials

    class DummyLogging:
        WARNING = "warning"

        @staticmethod
        def get_verbosity():
            return "info"

        @staticmethod
        def set_verbosity(value):
            return None

    class DummyOptunaModule:
        samplers = DummySamplers()
        logging = DummyLogging()

        @staticmethod
        def create_study(direction, sampler):
            return DummyStudy()

    monkeypatch.setattr("testsavant.guard.optimization.importlib.import_module", lambda name: DummyOptunaModule())

    optimizer = OptunaOptimizer(top_k=2, seed=7, exploration_ratio=1.0, min_exploration_trials=1)
    results = optimizer.optimize(
        search_space={
            "threshold": [(0.2, 0.0), (0.8, 1.0)],
            "chunk_size": [(50, 0.0), (100, 1.0)],
        },
        score_fn=lambda config: 1.0 if config == {"threshold": 0.2, "chunk_size": 50} else (0.7 if config == {"threshold": 0.8, "chunk_size": 100} else 0.4),
        epochs=1,
        steps_per_epoch=4,
    )

    assert results[0]["config"] == {"threshold": 0.2, "chunk_size": 50}
    assert results[0]["mean_score"] == 1.0


def test_optuna_optimizer_uses_preferences_for_objective_tiebreak(monkeypatch):
    class DummyTrial:
        def __init__(self, number):
            self.number = number
            self.user_attrs = {}

        def suggest_categorical(self, name, values):
            return values[0]

        def set_user_attr(self, key, value):
            self.user_attrs[key] = value

    class DummyStudy:
        def __init__(self):
            self.trials = []

        def optimize(self, objective, n_trials, callbacks):
            for number in range(n_trials):
                trial = DummyTrial(number)
                objective(trial)
                self.trials.append(trial)
                for callback in callbacks:
                    callback(self, trial)

    class DummySamplers:
        class TPESampler:
            def __init__(self, seed, n_startup_trials=0):
                self.seed = seed
                self.n_startup_trials = n_startup_trials

    class DummyLogging:
        WARNING = "warning"

        @staticmethod
        def get_verbosity():
            return "info"

        @staticmethod
        def set_verbosity(value):
            return None

    class DummyOptunaModule:
        samplers = DummySamplers()
        logging = DummyLogging()

        @staticmethod
        def create_study(direction, sampler):
            return DummyStudy()

    monkeypatch.setattr("testsavant.guard.optimization.importlib.import_module", lambda name: DummyOptunaModule())

    optimizer = OptunaOptimizer(top_k=4, seed=3, exploration_ratio=1.0, min_exploration_trials=1, preference_strength=0.1, preference_mode="objective")
    results = optimizer.optimize(
        search_space={
            "threshold": [(0.2, 0.0), (0.8, 1.0)],
            "chunk_size": [(50, 0.0), (100, 1.0)],
        },
        score_fn=lambda config: 0.5,
        epochs=1,
        steps_per_epoch=4,
    )

    assert results[0]["config"] == {"threshold": 0.8, "chunk_size": 100}
    assert results[0]["objective_score"] > results[0]["mean_score"]


def test_optuna_optimizer_supports_sample_batches(monkeypatch):
    batches = [[1.0, 1.0], [2.0, 2.0]]

    class DummyTrial:
        def __init__(self, number):
            self.number = number
            self.user_attrs = {}

        def suggest_categorical(self, name, values):
            return values[0]

        def set_user_attr(self, key, value):
            self.user_attrs[key] = value

    class DummyStudy:
        def __init__(self):
            self.trials = []

        def optimize(self, objective, n_trials, callbacks):
            for number in range(n_trials):
                trial = DummyTrial(number)
                objective(trial)
                self.trials.append(trial)
                for callback in callbacks:
                    callback(self, trial)

    class DummySamplers:
        class TPESampler:
            def __init__(self, seed, n_startup_trials=0):
                self.seed = seed
                self.n_startup_trials = n_startup_trials

    class DummyLogging:
        WARNING = "warning"

        @staticmethod
        def get_verbosity():
            return "info"

        @staticmethod
        def set_verbosity(value):
            return None

    class DummyOptunaModule:
        samplers = DummySamplers()
        logging = DummyLogging()

        @staticmethod
        def create_study(direction, sampler):
            return DummyStudy()

    monkeypatch.setattr("testsavant.guard.optimization.importlib.import_module", lambda name: DummyOptunaModule())

    def sample_batch_fn():
        return batches.pop(0) if batches else [1.5, 1.5]

    optimizer = OptunaOptimizer(top_k=2, seed=1, exploration_ratio=1.0, min_exploration_trials=1, preference_mode="none")
    results = optimizer.optimize(
        search_space={"threshold": [(0.25, 1.0), (0.5, 1.0)]},
        score_fn=lambda config, batch: config["threshold"] + sum(batch) / len(batch),
        sample_batch_fn=sample_batch_fn,
        epochs=1,
        steps_per_epoch=2,
    )

    assert len(results) == 2
    assert all(result["num_evals"] >= 1 for result in results)


def test_optuna_optimizer_supports_should_stop_and_matches_progress_shape(monkeypatch):
    events = []
    created_studies = []

    class DummyTrial:
        def __init__(self, number, params):
            self.number = number
            self._params = params
            self.user_attrs = {}

        def suggest_categorical(self, name, values):
            return self._params[name]

        def set_user_attr(self, key, value):
            self.user_attrs[key] = value

    class DummyStudy:
        def __init__(self):
            self.trials = []
            self.stop_called = False

        def stop(self):
            self.stop_called = True

        def optimize(self, objective, n_trials, callbacks):
            planned_params = [
                {"threshold": 0.25},
                {"threshold": 0.5},
                {"threshold": 0.25},
            ]
            for number, params in enumerate(planned_params[:n_trials]):
                trial = DummyTrial(number, params)
                objective(trial)
                self.trials.append(trial)
                for callback in callbacks:
                    callback(self, trial)
                if self.stop_called:
                    break

    class DummySamplers:
        class TPESampler:
            def __init__(self, seed):
                self.seed = seed

    class DummyLogging:
        WARNING = "warning"

        @staticmethod
        def get_verbosity():
            return "info"

        @staticmethod
        def set_verbosity(value):
            return None

    class DummyOptunaModule:
        samplers = DummySamplers()
        logging = DummyLogging()

        @staticmethod
        def create_study(direction, sampler):
            study = DummyStudy()
            created_studies.append(study)
            return study

    monkeypatch.setattr("testsavant.guard.optimization.importlib.import_module", lambda name: DummyOptunaModule())

    optimizer = OptunaOptimizer(top_k=1, seed=1)
    optimizer.optimize(
        search_space={"threshold": [(0.25, 0.0), (0.5, 1.0)]},
        score_fn=lambda config: 1.0 if config["threshold"] == 0.25 else 0.2,
        epochs=1,
        steps_per_epoch=3,
        on_step=events.append,
        should_stop=lambda payload: payload["step"] >= 2,
    )

    assert len(events) == 2
    assert events[0]["step"] == 1
    assert events[0]["epoch"] == 1
    assert events[0]["step_in_epoch"] == 1
    assert events[0]["candidate_results"]
    assert events[0]["top_results"]
    assert created_studies[0].stop_called is True


def test_optuna_optimizer_explores_unique_configs_before_revisiting(monkeypatch):
    seen_configs = []

    class DummyTrial:
        def __init__(self, number):
            self.number = number
            self.user_attrs = {}

        def suggest_categorical(self, name, values):
            return values[0]

        def set_user_attr(self, key, value):
            self.user_attrs[key] = value

    class DummyStudy:
        def __init__(self):
            self.trials = []

        def optimize(self, objective, n_trials, callbacks):
            for number in range(n_trials):
                trial = DummyTrial(number)
                objective(trial)
                seen_configs.append(trial.user_attrs["config"])
                self.trials.append(trial)
                for callback in callbacks:
                    callback(self, trial)

    class DummySamplers:
        class TPESampler:
            def __init__(self, seed, n_startup_trials=0):
                self.seed = seed
                self.n_startup_trials = n_startup_trials

    class DummyLogging:
        WARNING = "warning"

        @staticmethod
        def get_verbosity():
            return "info"

        @staticmethod
        def set_verbosity(value):
            return None

    class DummyOptunaModule:
        samplers = DummySamplers()
        logging = DummyLogging()

        @staticmethod
        def create_study(direction, sampler):
            return DummyStudy()

    monkeypatch.setattr("testsavant.guard.optimization.importlib.import_module", lambda name: DummyOptunaModule())

    optimizer = OptunaOptimizer(top_k=4, seed=5, exploration_ratio=1.0, min_exploration_trials=1)
    optimizer.optimize(
        search_space={
            "threshold": [(0.25, 0.0), (0.5, 0.0)],
            "chunk_size": [(50, 0.0), (100, 0.0)],
        },
        score_fn=lambda config: config["threshold"],
        epochs=1,
        steps_per_epoch=4,
    )

    assert len(seen_configs) == 4
    assert len({tuple(sorted(config.items())) for config in seen_configs}) == 4