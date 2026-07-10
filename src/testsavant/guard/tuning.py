from dataclasses import dataclass
import math
import random
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Type

from .guard import InputGuard
from .input_scanners import Scanner
from .optimization import ConfigDict, DiscreteBanditOptimizer, SearchSpace, create_optimizer


PredictValidFn = Callable[[ConfigDict, Sequence[str]], Sequence[bool]]
InputScannerFactory = Callable[[ConfigDict], Scanner]


class ConfigOptimizer(Protocol):
    def optimize(
        self,
        search_space: SearchSpace,
        score_fn: Callable[..., float],
        epochs: int = 10,
        steps_per_epoch: int = 100,
        sample_batch_fn: Optional[Callable[[], Any]] = None,
        on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        ...


def _safe_divide(numerator: float, denominator: float) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def harmonic_mean(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None or (left + right) == 0:
        return None
    return 2 * (left * right) / (left + right)


@dataclass
class BinaryClassificationMetrics:
    total_count: int
    valid_count: int
    invalid_count: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    recall: Optional[float]
    specificity: Optional[float]
    precision: Optional[float]
    f1_score: Optional[float]
    false_positive_rate: Optional[float]
    false_negative_rate: Optional[float]
    accuracy: Optional[float]
    effectiveness_score: Optional[float]
    selection_score: float
    predicted_valid_count: int
    predicted_invalid_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_count": self.total_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "true_negative": self.true_negative,
            "false_negative": self.false_negative,
            "recall": self.recall,
            "specificity": self.specificity,
            "precision": self.precision,
            "f1_score": self.f1_score,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
            "accuracy": self.accuracy,
            "effectiveness_score": self.effectiveness_score,
            "selection_score": self.selection_score,
            "predicted_valid_count": self.predicted_valid_count,
            "predicted_invalid_count": self.predicted_invalid_count,
        }


@dataclass
class GuardrailCandidateResult:
    config: ConfigDict
    optimization_result: Dict[str, Any]
    train_metrics: BinaryClassificationMetrics
    report_metrics: BinaryClassificationMetrics
    test_metrics: Optional[BinaryClassificationMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config,
            "optimization_result": self.optimization_result,
            "train_metrics": self.train_metrics.to_dict(),
            "report_metrics": self.report_metrics.to_dict(),
            "test_metrics": self.test_metrics.to_dict() if self.test_metrics is not None else None,
        }


@dataclass
class GuardrailFitResult:
    best_config: ConfigDict
    best_train_metrics: BinaryClassificationMetrics
    best_report_metrics: BinaryClassificationMetrics
    report_split_name: str
    candidate_results: List[GuardrailCandidateResult]
    epochs: int
    batch_size: int
    steps_per_epoch: int
    best_test_metrics: Optional[BinaryClassificationMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_config": self.best_config,
            "best_train_metrics": self.best_train_metrics.to_dict(),
            "best_report_metrics": self.best_report_metrics.to_dict(),
            "report_split_name": self.report_split_name,
            "candidate_results": [candidate.to_dict() for candidate in self.candidate_results],
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "steps_per_epoch": self.steps_per_epoch,
            "best_test_metrics": self.best_test_metrics.to_dict() if self.best_test_metrics is not None else None,
        }


def compute_binary_classification_metrics(
    true_valid_labels: Sequence[bool],
    predicted_valid_labels: Sequence[bool],
) -> BinaryClassificationMetrics:
    if len(true_valid_labels) != len(predicted_valid_labels):
        raise ValueError("true_valid_labels and predicted_valid_labels must have the same length.")
    if not true_valid_labels:
        raise ValueError("At least one label is required to compute metrics.")

    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0

    for actual_valid, predicted_valid in zip(true_valid_labels, predicted_valid_labels):
        actual_invalid = not actual_valid
        predicted_invalid = not predicted_valid

        if actual_invalid and predicted_invalid:
            true_positive += 1
        elif (not actual_invalid) and predicted_invalid:
            false_positive += 1
        elif (not actual_invalid) and (not predicted_invalid):
            true_negative += 1
        else:
            false_negative += 1

    total_count = len(true_valid_labels)
    valid_count = sum(1 for label in true_valid_labels if label)
    invalid_count = total_count - valid_count
    predicted_invalid_count = true_positive + false_positive
    predicted_valid_count = true_negative + false_negative

    recall = _safe_divide(true_positive, invalid_count)
    specificity = _safe_divide(true_negative, valid_count)
    precision = _safe_divide(true_positive, predicted_invalid_count)
    f1_score = harmonic_mean(precision, recall)
    false_positive_rate = _safe_divide(false_positive, valid_count)
    false_negative_rate = _safe_divide(false_negative, invalid_count)
    accuracy = _safe_divide(true_positive + true_negative, total_count)
    effectiveness_score = harmonic_mean(recall, specificity)

    if effectiveness_score is not None:
        selection_score = effectiveness_score
    elif recall is not None:
        selection_score = recall
    elif specificity is not None:
        selection_score = specificity
    else:
        selection_score = float("-inf")

    return BinaryClassificationMetrics(
        total_count=total_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        recall=recall,
        specificity=specificity,
        precision=precision,
        f1_score=f1_score,
        false_positive_rate=false_positive_rate,
        false_negative_rate=false_negative_rate,
        accuracy=accuracy,
        effectiveness_score=effectiveness_score,
        selection_score=selection_score,
        predicted_valid_count=predicted_valid_count,
        predicted_invalid_count=predicted_invalid_count,
    )


class BinaryGuardrailTuner:
    """Generic tuner for validity-based binary guardrails."""

    def __init__(
        self,
        search_space: SearchSpace,
        predict_valid_fn: PredictValidFn,
        optimizer: Optional[ConfigOptimizer] = None,
        top_k: int = 10,
        random_state: int = 42,
    ) -> None:
        self.search_space = search_space
        self.predict_valid_fn = predict_valid_fn
        self.optimizer = optimizer or DiscreteBanditOptimizer(top_k=top_k, seed=random_state)
        self.top_k = top_k
        self.random_state = random_state

    @staticmethod
    def resolve_optimizer(
        optimizer: Optional[ConfigOptimizer] = None,
        optimizer_name: str = "bandit",
        top_k: int = 10,
        random_state: int = 42,
    ) -> ConfigOptimizer:
        if optimizer is not None:
            return optimizer
        return create_optimizer(optimizer_name, top_k=top_k, seed=random_state)

    @classmethod
    def from_input_scanner(
        cls,
        search_space: SearchSpace,
        scanner_factory: InputScannerFactory,
        optimizer: Optional[ConfigOptimizer] = None,
        top_k: int = 10,
        random_state: int = 42,
        API_KEY: Optional[str] = None,
        PROJECT_ID: Optional[str] = None,
        remote_addr: Optional[str] = None,
        fail_fast: bool = True,
    ) -> "BinaryGuardrailTuner":
        def predict_valid_fn(config: ConfigDict, inputs: Sequence[str]) -> Sequence[bool]:
            guard = InputGuard(
                API_KEY=API_KEY,
                PROJECT_ID=PROJECT_ID,
                remote_addr=remote_addr,
                fail_fast=fail_fast,
            )
            guard.add_scanner(scanner_factory(config))
            return [guard.scan(text, is_async=False).is_valid for text in inputs]

        return cls(
            search_space=search_space,
            predict_valid_fn=predict_valid_fn,
            optimizer=optimizer,
            top_k=top_k,
            random_state=random_state,
        )

    @classmethod
    def from_input_scanner_class(
        cls,
        scanner_cls: Type[Scanner],
        fixed_scanner_kwargs: Optional[Dict[str, Any]] = None,
        optimizer: Optional[ConfigOptimizer] = None,
        optimizer_name: str = "bandit",
        top_k: Optional[int] = None,
        random_state: int = 42,
        API_KEY: Optional[str] = None,
        PROJECT_ID: Optional[str] = None,
        remote_addr: Optional[str] = None,
        fail_fast: bool = True,
    ) -> "BinaryGuardrailTuner":
        optimization_defaults = scanner_cls.get_optimization_defaults()
        resolved_top_k = top_k if top_k is not None else int(optimization_defaults.get("top_k", 10))
        resolved_fixed_scanner_kwargs = dict(fixed_scanner_kwargs or {})

        return cls.from_input_scanner(
            search_space=scanner_cls.get_optimization_search_space(),
            scanner_factory=lambda config: scanner_cls.build_optimized_instance(
                config,
                fixed_kwargs=resolved_fixed_scanner_kwargs,
            ),
            optimizer=cls.resolve_optimizer(
                optimizer=optimizer,
                optimizer_name=optimizer_name,
                top_k=resolved_top_k,
                random_state=random_state,
            ),
            top_k=resolved_top_k,
            random_state=random_state,
            API_KEY=API_KEY,
            PROJECT_ID=PROJECT_ID,
            remote_addr=remote_addr,
            fail_fast=fail_fast,
        )

    def _validate_dataset(self, inputs: Sequence[str], labels: Sequence[bool], dataset_name: str) -> None:
        if len(inputs) != len(labels):
            raise ValueError(f"{dataset_name} inputs and labels must have the same length.")
        if not inputs:
            raise ValueError(f"{dataset_name} must contain at least one example.")
        if not all(isinstance(text, str) for text in inputs):
            raise ValueError(f"{dataset_name} inputs must be strings.")
        if not all(isinstance(label, bool) for label in labels):
            raise ValueError(f"{dataset_name} labels must be bool values where True=valid and False=invalid.")

    def evaluate(self, config: ConfigDict, inputs: Sequence[str], labels: Sequence[bool]) -> BinaryClassificationMetrics:
        self._validate_dataset(inputs, labels, "evaluation dataset")
        predicted_valid_labels = list(self.predict_valid_fn(config, inputs))
        if len(predicted_valid_labels) != len(inputs):
            raise ValueError("predict_valid_fn must return one boolean prediction for each input.")
        if not all(isinstance(label, bool) for label in predicted_valid_labels):
            raise ValueError("predict_valid_fn must return boolean validity predictions.")
        return compute_binary_classification_metrics(labels, predicted_valid_labels)

    def fit(
        self,
        train_x: Sequence[str],
        train_y: Sequence[bool],
        test_x: Optional[Sequence[str]] = None,
        test_y: Optional[Sequence[bool]] = None,
        epochs: int = 10,
        batch_size: int = 32,
        on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> GuardrailFitResult:
        self._validate_dataset(train_x, train_y, "train dataset")

        has_test_set = test_x is not None or test_y is not None
        if has_test_set:
            if test_x is None or test_y is None:
                raise ValueError("Both test_x and test_y must be provided together.")
            self._validate_dataset(test_x, test_y, "test dataset")

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")

        steps_per_epoch = max(1, math.ceil(len(train_x) / batch_size))
        rng = random.Random(self.random_state)
        train_examples = list(zip(train_x, train_y))

        def sample_batch_fn() -> List[Any]:
            if len(train_examples) <= batch_size:
                return train_examples
            batch_indices = rng.sample(range(len(train_examples)), batch_size)
            return [train_examples[index] for index in batch_indices]

        def score_fn(config: ConfigDict, batch: Sequence[Any]) -> float:
            batch_inputs = [text for text, _ in batch]
            batch_labels = [label for _, label in batch]
            metrics = self.evaluate(config, batch_inputs, batch_labels)
            return metrics.selection_score

        optimization_results = self.optimizer.optimize(
            search_space=self.search_space,
            score_fn=score_fn,
            epochs=epochs,
            steps_per_epoch=steps_per_epoch,
            sample_batch_fn=sample_batch_fn,
            on_step=on_step,
            top_k=self.top_k,
        )

        candidate_results: List[GuardrailCandidateResult] = []
        for optimization_result in optimization_results:
            config = dict(optimization_result["config"])
            train_metrics = self.evaluate(config, train_x, train_y)
            test_metrics = self.evaluate(config, test_x, test_y) if has_test_set else None
            report_metrics = test_metrics if test_metrics is not None else train_metrics
            candidate_results.append(
                GuardrailCandidateResult(
                    config=config,
                    optimization_result=optimization_result,
                    train_metrics=train_metrics,
                    report_metrics=report_metrics,
                    test_metrics=test_metrics,
                )
            )

        best_candidate = max(
            candidate_results,
            key=lambda candidate: (
                candidate.report_metrics.selection_score,
                candidate.train_metrics.selection_score,
                candidate.optimization_result.get("objective_score", float("-inf")),
            ),
        )

        return GuardrailFitResult(
            best_config=best_candidate.config,
            best_train_metrics=best_candidate.train_metrics,
            best_report_metrics=best_candidate.report_metrics,
            report_split_name="test" if has_test_set else "train",
            candidate_results=candidate_results,
            epochs=epochs,
            batch_size=batch_size,
            steps_per_epoch=steps_per_epoch,
            best_test_metrics=best_candidate.test_metrics,
        )


__all__ = [
    "BinaryClassificationMetrics",
    "BinaryGuardrailTuner",
    "ConfigOptimizer",
    "GuardrailCandidateResult",
    "GuardrailFitResult",
    "compute_binary_classification_metrics",
    "harmonic_mean",
]