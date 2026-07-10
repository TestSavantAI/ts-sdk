import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
sys.modules.setdefault("requests", types.ModuleType("requests"))
fake_httpx = types.ModuleType("httpx")
fake_httpx.AsyncClient = object
fake_httpx.Client = object
sys.modules.setdefault("httpx", fake_httpx)

from testsavant.guard import OptunaOptimizer, build_discrete_configs, discrete_bandit_optimize


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


def test_discrete_bandit_optimize_prefers_best_raw_score_when_scores_are_separated():
    search_space = {
        "threshold": [(0.2, 0.0), (0.8, 1.0)],
        "chunk_size": [(50, 0.0), (100, 1.0)],
    }

    def score_fn(config):
        if config == {"threshold": 0.2, "chunk_size": 50}:
            return 1.0
        if config == {"threshold": 0.8, "chunk_size": 100}:
            return 0.7
        return 0.4

    results = discrete_bandit_optimize(
        search_space=search_space,
        score_fn=score_fn,
        epochs=3,
        steps_per_epoch=4,
        configs_per_step=2,
        preference_strength=0.2,
        preference_mode="objective",
        top_k=2,
        seed=7,
    )

    assert results[0]["config"] == {"threshold": 0.2, "chunk_size": 50}
    assert results[0]["mean_score"] == 1.0


def test_discrete_bandit_optimize_uses_preferences_for_objective_tiebreak():
    search_space = {
        "threshold": [(0.2, 0.0), (0.8, 1.0)],
        "chunk_size": [(50, 0.0), (100, 1.0)],
    }

    def score_fn(config):
        return 0.5

    results = discrete_bandit_optimize(
        search_space=search_space,
        score_fn=score_fn,
        epochs=2,
        steps_per_epoch=4,
        configs_per_step=2,
        preference_strength=0.1,
        preference_mode="objective",
        top_k=4,
        seed=3,
    )

    assert results[0]["config"] == {"threshold": 0.8, "chunk_size": 100}
    assert results[0]["objective_score"] > results[0]["mean_score"]


def test_discrete_bandit_optimize_supports_sample_batches():
    search_space = {
        "threshold": [(0.25, 1.0), (0.5, 1.0)],
    }

    batches = [[1.0, 1.0], [2.0, 2.0]]

    def sample_batch_fn():
        return batches.pop(0) if batches else [1.5, 1.5]

    def score_fn(config, batch):
        return config["threshold"] + sum(batch) / len(batch)

    results = discrete_bandit_optimize(
        search_space=search_space,
        score_fn=score_fn,
        sample_batch_fn=sample_batch_fn,
        epochs=1,
        steps_per_epoch=2,
        configs_per_step=1,
        preference_mode="none",
        top_k=2,
        seed=1,
    )

    assert len(results) == 2
    assert all(result["num_evals"] >= 1 for result in results)


def test_discrete_bandit_optimize_calls_on_step_with_progress_payload():
    search_space = {
        "threshold": [(0.25, 1.0), (0.5, 1.0)],
    }

    events = []

    def score_fn(config):
        return config["threshold"]

    def on_step(payload):
        events.append(payload)

    results = discrete_bandit_optimize(
        search_space=search_space,
        score_fn=score_fn,
        epochs=2,
        steps_per_epoch=2,
        configs_per_step=1,
        preference_mode="none",
        top_k=1,
        seed=1,
        on_step=on_step,
    )

    assert len(events) == 4
    assert events[0]["step"] == 1
    assert events[-1]["step"] == 4
    assert events[-1]["epoch"] == 2
    assert events[-1]["step_in_epoch"] == 2
    assert events[-1]["top_results"][0]["config"] == results[0]["config"]
    assert events[-1]["candidate_results"]


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

    class DummySamplers:
        class TPESampler:
            def __init__(self, seed):
                self.seed = seed

    class DummyOptunaModule:
        samplers = DummySamplers()

        @staticmethod
        def create_study(direction, sampler):
            return DummyStudy()

    monkeypatch.setattr("testsavant.guard.optimization.importlib.import_module", lambda name: DummyOptunaModule())

    optimizer = OptunaOptimizer(top_k=2, seed=1)
    results = optimizer.optimize(
        search_space={"threshold": [(0.25, 0.0), (0.5, 1.0)]},
        score_fn=lambda config: 1.0 if config["threshold"] == 0.25 else 0.2,
        epochs=1,
        steps_per_epoch=3,
    )

    assert len(results) == 2
    assert results[0]["config"] == {"threshold": 0.25}
    assert results[0]["num_evals"] == 2
    assert results[0]["mean_score"] == 1.0