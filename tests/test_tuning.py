import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
sys.modules.setdefault("requests", types.ModuleType("requests"))
fake_httpx = types.ModuleType("httpx")
fake_httpx.AsyncClient = object
fake_httpx.Client = object
sys.modules.setdefault("httpx", fake_httpx)

from testsavant.guard import BinaryGuardrailTuner, compute_binary_classification_metrics, create_optimizer
from testsavant.guard.input_scanners import BanTopics, PromptInjection


def test_compute_binary_classification_metrics_uses_invalid_as_positive_class():
    metrics = compute_binary_classification_metrics(
        true_valid_labels=[True, True, False, False],
        predicted_valid_labels=[True, False, False, True],
    )

    assert metrics.true_positive == 1
    assert metrics.false_positive == 1
    assert metrics.true_negative == 1
    assert metrics.false_negative == 1
    assert metrics.recall == 0.5
    assert metrics.specificity == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.false_negative_rate == 0.5
    assert metrics.effectiveness_score == 0.5


class DummyOptimizer:
    def __init__(self):
        self.calls = []

    def optimize(
        self,
        search_space,
        score_fn,
        epochs=10,
        steps_per_epoch=100,
        sample_batch_fn=None,
        on_step=None,
        should_stop=None,
        top_k=None,
    ):
        self.calls.append(
            {
                "epochs": epochs,
                "steps_per_epoch": steps_per_epoch,
                "top_k": top_k,
            }
        )

        if sample_batch_fn is not None:
            batch = sample_batch_fn()
            score_fn({"block_bad": True, "block_unsafe": True}, batch)

        step_payload = {
            "step": 1,
            "total_steps": steps_per_epoch,
            "epoch": 1,
            "step_in_epoch": 1,
            "steps_per_epoch": steps_per_epoch,
            "total_evals": 1,
            "candidate_results": [],
            "top_results": [],
        }
        if on_step is not None:
            on_step(step_payload)
        if should_stop is not None:
            should_stop(step_payload)

        return [
            {
                "config": {"block_bad": False, "block_unsafe": True},
                "mean_score": 0.2,
                "std_score": 0.0,
                "num_evals": 1,
                "preference_score": 0.0,
                "objective_score": 0.2,
            },
            {
                "config": {"block_bad": True, "block_unsafe": True},
                "mean_score": 0.9,
                "std_score": 0.0,
                "num_evals": 1,
                "preference_score": 0.0,
                "objective_score": 0.9,
            },
        ]


def test_binary_guardrail_tuner_uses_replaceable_optimizer_and_returns_best_config():
    optimizer = DummyOptimizer()
    events = []

    def predict_valid_fn(config, inputs):
        outputs = []
        for text in inputs:
            is_invalid = False
            if config.get("block_bad") and "bad" in text:
                is_invalid = True
            if config.get("block_unsafe") and "unsafe" in text:
                is_invalid = True
            outputs.append(not is_invalid)
        return outputs

    tuner = BinaryGuardrailTuner(
        search_space={
            "block_bad": [(False, 0.0), (True, 1.0)],
            "block_unsafe": [(False, 0.0), (True, 1.0)],
        },
        predict_valid_fn=predict_valid_fn,
        optimizer=optimizer,
        top_k=2,
        random_state=7,
    )

    result = tuner.fit(
        train_x=["good", "bad prompt", "unsafe request", "safe text"],
        train_y=[True, False, False, True],
        test_x=["bad prompt", "unsafe request", "completely safe"],
        test_y=[False, False, True],
        epochs=3,
        batch_size=2,
        on_step=events.append,
    )

    assert optimizer.calls[0]["epochs"] == 3
    assert optimizer.calls[0]["steps_per_epoch"] == 2
    assert result.best_config == {"block_bad": True, "block_unsafe": True}
    assert result.best_eval_result.effectiveness_score == 1.0
    assert result.best_eval_result.f1_score == 1.0
    assert result.best_eval_result.false_positive_rate == 0.0
    assert len(result.candidate_results) == 2
    assert len(events) == 1


def test_binary_guardrail_tuner_reports_train_metrics_when_test_set_is_absent():
    class SingleConfigOptimizer:
        def optimize(
            self,
            search_space,
            score_fn,
            epochs=10,
            steps_per_epoch=100,
            sample_batch_fn=None,
            on_step=None,
            should_stop=None,
            top_k=None,
        ):
            return [
                {
                    "config": {"block_bad": True},
                    "mean_score": 1.0,
                    "std_score": 0.0,
                    "num_evals": 1,
                    "preference_score": 0.0,
                    "objective_score": 1.0,
                }
            ]

    def predict_valid_fn(config, inputs):
        return [not (config["block_bad"] and "bad" in text) for text in inputs]

    tuner = BinaryGuardrailTuner(
        search_space={"block_bad": [(False, 0.0), (True, 1.0)]},
        predict_valid_fn=predict_valid_fn,
        optimizer=SingleConfigOptimizer(),
        top_k=1,
        random_state=1,
    )

    result = tuner.fit(
        train_x=["good", "bad prompt"],
        train_y=[True, False],
        epochs=1,
        batch_size=2,
    )

    assert result.best_eval_result.effectiveness_score == 1.0


def test_binary_guardrail_tuner_selects_winner_from_train_then_reports_test_eval():
    class FixedOptimizer:
        def optimize(
            self,
            search_space,
            score_fn,
            epochs=10,
            steps_per_epoch=100,
            sample_batch_fn=None,
            on_step=None,
            top_k=None,
        ):
            return [
                {
                    "config": {"mode": "train_best"},
                    "mean_score": 0.9,
                    "std_score": 0.0,
                    "num_evals": 1,
                    "preference_score": 0.0,
                    "objective_score": 0.9,
                },
                {
                    "config": {"mode": "test_best"},
                    "mean_score": 0.8,
                    "std_score": 0.0,
                    "num_evals": 1,
                    "preference_score": 0.0,
                    "objective_score": 0.8,
                },
            ]

    predictions = {
        ("train_best", "bad train"): False,
        ("train_best", "safe train"): True,
        ("train_best", "bad test"): True,
        ("train_best", "safe test"): True,
        ("test_best", "bad train"): True,
        ("test_best", "safe train"): True,
        ("test_best", "bad test"): False,
        ("test_best", "safe test"): True,
    }

    def predict_valid_fn(config, inputs):
        mode = config["mode"]
        return [predictions[(mode, text)] for text in inputs]

    tuner = BinaryGuardrailTuner(
        search_space={"mode": [("train_best", 0.0), ("test_best", 0.0)]},
        predict_valid_fn=predict_valid_fn,
        optimizer=FixedOptimizer(),
        top_k=2,
        random_state=1,
    )

    result = tuner.fit(
        train_x=["bad train", "safe train"],
        train_y=[False, True],
        test_x=["bad test", "safe test"],
        test_y=[False, True],
        epochs=1,
        batch_size=2,
    )

    assert result.best_config == {"mode": "train_best"}
    assert result.best_eval_result.effectiveness_score == 0.0


def test_binary_guardrail_tuner_stops_early_when_test_score_stalls():
    class EarlyStoppingOptimizer:
        def __init__(self):
            self.steps_seen = 0

        def optimize(
            self,
            search_space,
            score_fn,
            epochs=10,
            steps_per_epoch=100,
            sample_batch_fn=None,
            on_step=None,
            should_stop=None,
            top_k=None,
        ):
            step_payloads = [
                {
                    "step": 1,
                    "total_steps": 5,
                    "epoch": 1,
                    "step_in_epoch": 1,
                    "steps_per_epoch": 5,
                    "total_evals": 1,
                    "candidate_results": [],
                    "top_results": [{"config": {"mode": "improve_once"}, "mean_score": 0.7, "std_score": 0.0, "num_evals": 1, "preference_score": 0.0, "objective_score": 0.7}],
                },
                {
                    "step": 2,
                    "total_steps": 5,
                    "epoch": 1,
                    "step_in_epoch": 2,
                    "steps_per_epoch": 5,
                    "total_evals": 2,
                    "candidate_results": [],
                    "top_results": [{"config": {"mode": "stall"}, "mean_score": 0.8, "std_score": 0.0, "num_evals": 1, "preference_score": 0.0, "objective_score": 0.8}],
                },
                {
                    "step": 3,
                    "total_steps": 5,
                    "epoch": 1,
                    "step_in_epoch": 3,
                    "steps_per_epoch": 5,
                    "total_evals": 3,
                    "candidate_results": [],
                    "top_results": [{"config": {"mode": "stall"}, "mean_score": 0.85, "std_score": 0.0, "num_evals": 1, "preference_score": 0.0, "objective_score": 0.85}],
                },
            ]

            last_step_payload = None
            for step_payload in step_payloads:
                self.steps_seen += 1
                last_step_payload = step_payload
                if on_step is not None:
                    on_step(step_payload)
                if should_stop is not None and should_stop(step_payload):
                    break

            return [last_step_payload["top_results"][0]]

    predictions = {
        ("improve_once", "bad train"): False,
        ("improve_once", "safe train"): True,
        ("improve_once", "bad test"): False,
        ("improve_once", "safe test"): True,
        ("stall", "bad train"): False,
        ("stall", "safe train"): True,
        ("stall", "bad test"): True,
        ("stall", "safe test"): True,
    }

    def predict_valid_fn(config, inputs):
        mode = config["mode"]
        return [predictions[(mode, text)] for text in inputs]

    optimizer = EarlyStoppingOptimizer()
    events = []
    tuner = BinaryGuardrailTuner(
        search_space={"mode": [("improve_once", 0.0), ("stall", 0.0)]},
        predict_valid_fn=predict_valid_fn,
        optimizer=optimizer,
        top_k=1,
        random_state=1,
    )

    result = tuner.fit(
        train_x=["bad train", "safe train"],
        train_y=[False, True],
        test_x=["bad test", "safe test"],
        test_y=[False, True],
        epochs=1,
        batch_size=2,
        patience=2,
        on_step=events.append,
    )

    assert optimizer.steps_seen == 3
    assert len(events) == 3
    assert events[0]["best_test_selection_score"] == 1.0
    assert events[1]["best_test_selection_score"] == 0.0
    assert events[2]["best_test_selection_score"] == 0.0
    assert result.best_config == {"mode": "stall"}
    assert result.best_eval_result.effectiveness_score == 0.0


def test_prompt_injection_defines_scanner_owned_optimization_spec():
    search_space = PromptInjection.get_optimization_search_space()
    defaults = PromptInjection.get_optimization_defaults()
    scanner = PromptInjection.build_optimized_instance(
        {"threshold": 0.5, "chunk_size": 300, "overlap": 10}
    )

    assert "threshold" in search_space
    assert "chunk_size" in search_space
    assert "overlap" in search_space
    assert defaults["batch_size"] == 32
    assert scanner.tag == "base"


def test_build_optimized_instance_accepts_fixed_scanner_kwargs():
    scanner = BanTopics.build_optimized_instance(
        {"threshold": 0.5},
        fixed_kwargs={"topics": ["finance"], "mode": "blacklist", "tag": "base"},
    )

    assert scanner.topics == ["finance"]
    assert scanner.mode == "blacklist"
    assert scanner.tag == "base"


def test_from_input_scanner_class_passes_fixed_scanner_kwargs(monkeypatch):
    captured = {}

    class DummyScanResult:
        def __init__(self, is_valid):
            self.is_valid = is_valid

    def fake_add_scanner(self, scanner):
        captured["scanner"] = scanner
        self.scanners = [scanner]

    def fake_scan(self, text, is_async=False):
        return DummyScanResult(is_valid=True)

    monkeypatch.setattr("testsavant.guard.guard.InputGuard.add_scanner", fake_add_scanner)
    monkeypatch.setattr("testsavant.guard.guard.InputGuard.scan", fake_scan)
    monkeypatch.setenv("TEST_SAVANT_API_KEY", "test-key")

    class NoOpOptimizer:
        def optimize(
            self,
            search_space,
            score_fn,
            epochs=10,
            steps_per_epoch=100,
            sample_batch_fn=None,
            on_step=None,
            should_stop=None,
            top_k=None,
        ):
            return []

    tuner = BinaryGuardrailTuner.from_input_scanner_class(
        scanner_cls=BanTopics,
        fixed_scanner_kwargs={"topics": ["finance"], "mode": "blacklist", "tag": "base"},
        optimizer=NoOpOptimizer(),
        random_state=1,
    )

    tuner.evaluate({"threshold": 0.4}, ["market update"], [True])

    assert captured["scanner"].topics == ["finance"]
    assert captured["scanner"].mode == "blacklist"
    assert captured["scanner"].threshold == 0.4