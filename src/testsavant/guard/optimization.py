from dataclasses import dataclass
import importlib
from itertools import product
from math import log, sqrt
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


PreferenceOption = Tuple[Any, float]
SearchSpace = Dict[str, Sequence[PreferenceOption]]
ConfigDict = Dict[str, Any]
ScannerOptimizationSpec = Dict[str, Any]


_DEFAULT_SCANNER_OPTIMIZATION_SPEC: ScannerOptimizationSpec = {
    "search_space": {
        "threshold": [(round(i * 0.025, 3), 1.0) for i in range(41)],
        "chunk_size": [
            (50, 0.1),
            (75, 0.2),
            (100, 0.3),
            (125, 0.4),
            (150, 0.5),
            (175, 0.6),
            (200, 0.7),
            (225, 0.8),
            (250, 0.9),
            (275, 1.0),
            (300, 1.0),
            (325, 1.0),
            (350, 1.0),
        ],
        "overlap": [
            (10, 1.0),
            (20, 0.8),
            (30, 0.5),
            (40, 0.3),
            (50, 0.1),
        ],
    },
    "init_kwargs": {"tag": "base"},
    "defaults": {
        "epochs": 8,
        "batch_size": 32,
        "top_k": 10,
    },
}


_SCANNER_OPTIMIZATION_SPECS: Dict[str, ScannerOptimizationSpec] = {
    "default": _DEFAULT_SCANNER_OPTIMIZATION_SPEC,
}


def _get_scanner_identifier(scanner_cls: Any) -> str:
    return f"{scanner_cls.__module__}.{scanner_cls.__name__}"


def get_scanner_optimization_spec(scanner_cls: Any) -> ScannerOptimizationSpec:
    scanner_name = _get_scanner_identifier(scanner_cls)
    return _SCANNER_OPTIMIZATION_SPECS.get(scanner_name, _SCANNER_OPTIMIZATION_SPECS["default"])


def get_scanner_optimization_search_space(scanner_cls: Any) -> SearchSpace:
    return dict(get_scanner_optimization_spec(scanner_cls)["search_space"])


def get_scanner_optimization_defaults(scanner_cls: Any) -> Dict[str, Any]:
    return dict(get_scanner_optimization_spec(scanner_cls).get("defaults", {}))


def build_optimized_scanner_instance(
    scanner_cls: Any,
    config: ConfigDict,
    fixed_kwargs: Optional[Dict[str, Any]] = None,
) -> Any:
    params = dict(get_scanner_optimization_spec(scanner_cls).get("init_kwargs", {}))
    if fixed_kwargs is not None:
        params.update(fixed_kwargs)
    params.update(config)
    return scanner_cls(**params)


@dataclass
class RunningStat:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def update(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        if self.n <= 1:
            return 0.0
        return self.m2 / (self.n - 1)

    @property
    def std(self) -> float:
        return sqrt(self.variance)


def _validate_search_space(search_space: SearchSpace) -> None:
    if not search_space:
        raise ValueError("search_space must contain at least one parameter.")

    for key, options in search_space.items():
        if not options:
            raise ValueError(f"search_space[{key!r}] must contain at least one option.")

        for option in options:
            if not isinstance(option, tuple) or len(option) != 2:
                raise ValueError(
                    f"Each option in search_space[{key!r}] must be a (value, preference_weight) tuple."
                )


def build_discrete_configs(search_space: SearchSpace) -> Tuple[List[ConfigDict], List[float]]:
    """
    Build the cartesian product of a discrete weighted search space.

    The search space must have the form:

    {
        "param_a": [(value1, weight1), (value2, weight2)],
        "param_b": [(value1, weight1), (value2, weight2)],
    }

    Returns a tuple of:
    - configs: a list of config dictionaries
    - preferences: normalized preference scores in the range [0, 1]
    """
    _validate_search_space(search_space)

    keys = list(search_space.keys())
    normalized_options: List[List[Tuple[Any, float]]] = []

    for key in keys:
        options = search_space[key]
        weights = [weight for _, weight in options]
        min_weight = min(weights)
        max_weight = max(weights)

        key_options: List[Tuple[Any, float]] = []
        for value, weight in options:
            if max_weight == min_weight:
                normalized_weight = 0.0
            else:
                normalized_weight = (weight - min_weight) / (max_weight - min_weight)
            key_options.append((value, normalized_weight))

        normalized_options.append(key_options)

    configs: List[ConfigDict] = []
    preferences: List[float] = []

    for combo in product(*normalized_options):
        config: ConfigDict = {}
        preference_sum = 0.0

        for key, (value, normalized_weight) in zip(keys, combo):
            config[key] = value
            preference_sum += normalized_weight

        configs.append(config)
        preferences.append(preference_sum / len(keys))

    return configs, preferences


def discrete_bandit_optimize(
    search_space: SearchSpace,
    score_fn: Callable[..., float],
    epochs: int = 10,
    steps_per_epoch: int = 100,
    configs_per_step: int = 8,
    sample_batch_fn: Optional[Callable[[], Any]] = None,
    on_step: Optional[Callable[[Dict[str, Any]], None]] = None,
    exploration_c: float = 1.5,
    preference_strength: float = 0.02,
    preference_mode: str = "objective",
    top_k: int = 10,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Generic stochastic bandit optimizer for discrete hyperparameter spaces.

    Parameters
    ----------
    search_space:
        Mapping from parameter name to a sequence of (value, preference_weight) tuples.
    score_fn:
        Function that receives a config dict and returns a score.
        If sample_batch_fn is provided, score_fn receives (config, batch).
    sample_batch_fn:
        Optional function that returns a mini-batch for stochastic evaluation.
    on_step:
        Optional callback invoked once after each optimization step. Receives a
        dictionary with step counters, candidate results, and current top results.
    preference_strength:
        Weight applied to the normalized preference score.
    preference_mode:
        One of "objective", "prior", or "none".
    """
    if preference_mode not in {"objective", "prior", "none"}:
        raise ValueError("preference_mode must be one of: 'objective', 'prior', 'none'.")
    if epochs <= 0:
        raise ValueError("epochs must be greater than 0.")
    if steps_per_epoch <= 0:
        raise ValueError("steps_per_epoch must be greater than 0.")
    if configs_per_step <= 0:
        raise ValueError("configs_per_step must be greater than 0.")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0.")

    rng = random.Random(seed)

    configs, preferences = build_discrete_configs(search_space)
    stats = [RunningStat() for _ in configs]
    total_evals = 0

    def adjusted_mean(index: int) -> float:
        value = stats[index].mean
        if preference_mode == "objective":
            value += preference_strength * preferences[index]
        return value

    def build_result(index: int) -> Dict[str, Any]:
        return {
            "config": configs[index],
            "mean_score": stats[index].mean,
            "std_score": stats[index].std,
            "num_evals": stats[index].n,
            "preference_score": preferences[index],
            "objective_score": adjusted_mean(index),
        }

    def ucb(index: int) -> float:
        if stats[index].n == 0:
            if preference_mode in {"objective", "prior"}:
                return float("inf") + preference_strength * preferences[index]
            return float("inf")

        bonus = exploration_c * sqrt(log(total_evals + 1) / stats[index].n)
        value = stats[index].mean + bonus

        if preference_mode in {"objective", "prior"}:
            value += preference_strength * preferences[index]

        return value

    total_steps = epochs * steps_per_epoch

    for step_index in range(total_steps):
        batch = sample_batch_fn() if sample_batch_fn is not None else None
        unseen_ids = [index for index, stat in enumerate(stats) if stat.n == 0]

        if unseen_ids:
            candidate_ids = rng.sample(unseen_ids, k=min(configs_per_step, len(unseen_ids)))
        else:
            candidate_ids = sorted(range(len(configs)), key=ucb, reverse=True)[:configs_per_step]

        for index in candidate_ids:
            config = configs[index]
            if batch is None:
                raw_score = score_fn(config)
            else:
                raw_score = score_fn(config, batch)

            stats[index].update(float(raw_score))
            total_evals += 1

        if on_step is not None:
            evaluated_ids = [index for index, stat in enumerate(stats) if stat.n > 0]
            if preference_mode == "objective":
                ranked_ids = sorted(evaluated_ids, key=adjusted_mean, reverse=True)
            else:
                ranked_ids = sorted(evaluated_ids, key=lambda index: stats[index].mean, reverse=True)

            on_step(
                {
                    "step": step_index + 1,
                    "total_steps": total_steps,
                    "epoch": step_index // steps_per_epoch + 1,
                    "steps_per_epoch": steps_per_epoch,
                    "step_in_epoch": step_index % steps_per_epoch + 1,
                    "total_evals": total_evals,
                    "candidate_results": [build_result(index) for index in candidate_ids],
                    "top_results": [build_result(index) for index in ranked_ids[:top_k]],
                }
            )

    ranked_ids = [index for index, stat in enumerate(stats) if stat.n > 0]

    if preference_mode == "objective":
        ranked_ids.sort(key=adjusted_mean, reverse=True)
    else:
        ranked_ids.sort(key=lambda index: stats[index].mean, reverse=True)

    results: List[Dict[str, Any]] = []
    for index in ranked_ids[:top_k]:
        results.append(build_result(index))

    return results


class DiscreteBanditOptimizer:
    """Config optimizer backed by the discrete bandit search implementation."""

    def __init__(
        self,
        configs_per_step: int = 8,
        exploration_c: float = 1.5,
        preference_strength: float = 0.02,
        preference_mode: str = "objective",
        top_k: int = 10,
        seed: int = 42,
    ) -> None:
        self.configs_per_step = configs_per_step
        self.exploration_c = exploration_c
        self.preference_strength = preference_strength
        self.preference_mode = preference_mode
        self.top_k = top_k
        self.seed = seed

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
        return discrete_bandit_optimize(
            search_space=search_space,
            score_fn=score_fn,
            epochs=epochs,
            steps_per_epoch=steps_per_epoch,
            configs_per_step=self.configs_per_step,
            sample_batch_fn=sample_batch_fn,
            on_step=on_step,
            exploration_c=self.exploration_c,
            preference_strength=self.preference_strength,
            preference_mode=self.preference_mode,
            top_k=self.top_k if top_k is None else top_k,
            seed=self.seed,
        )


class OptunaOptimizer:
    """Config optimizer backed by Optuna when it is available."""

    def __init__(
        self,
        top_k: int = 10,
        seed: int = 42,
        preference_strength: float = 0.02,
        preference_mode: str = "objective",
    ) -> None:
        self.top_k = top_k
        self.seed = seed
        self.preference_strength = preference_strength
        self.preference_mode = preference_mode

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
        try:
            optuna = importlib.import_module("optuna")
        except ImportError as exc:
            raise ImportError(
                "Optuna is not installed. Install optuna to use optimizer_name='optuna'."
            ) from exc

        if self.preference_mode not in {"objective", "prior", "none"}:
            raise ValueError("preference_mode must be one of: 'objective', 'prior', 'none'.")

        configs, preferences = build_discrete_configs(search_space)
        config_index = {tuple(sorted(config.items())): index for index, config in enumerate(configs)}
        target_top_k = self.top_k if top_k is None else top_k
        total_trials = epochs * steps_per_epoch
        stats_by_key: Dict[Tuple[Tuple[str, Any], ...], RunningStat] = {}

        def adjusted_mean(config_key: Tuple[Tuple[str, Any], ...]) -> float:
            index = config_index[config_key]
            mean_score = stats_by_key[config_key].mean
            if self.preference_mode == "objective":
                return mean_score + self.preference_strength * preferences[index]
            return mean_score

        def build_grouped_result(config_key: Tuple[Tuple[str, Any], ...]) -> Dict[str, Any]:
            index = config_index[config_key]
            stat = stats_by_key[config_key]
            return {
                "config": configs[index],
                "mean_score": stat.mean,
                "std_score": stat.std,
                "num_evals": stat.n,
                "preference_score": preferences[index],
                "objective_score": adjusted_mean(config_key),
            }

        def adjusted_score(index: int, mean_score: float) -> float:
            if self.preference_mode == "objective":
                return mean_score + self.preference_strength * preferences[index]
            return mean_score

        sampler = optuna.samplers.TPESampler(seed=self.seed)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        option_values = {key: [value for value, _ in options] for key, options in search_space.items()}

        def objective(trial):
            batch = sample_batch_fn() if sample_batch_fn is not None else None
            config = {
                key: trial.suggest_categorical(key, values)
                for key, values in option_values.items()
            }

            if batch is None:
                raw_score = float(score_fn(config))
            else:
                raw_score = float(score_fn(config, batch))

            index = config_index[tuple(sorted(config.items()))]
            objective_score = adjusted_score(index, raw_score) if self.preference_mode == "objective" else raw_score

            trial.set_user_attr("raw_score", raw_score)
            trial.set_user_attr("config", config)
            trial.set_user_attr("preference_score", preferences[index])
            trial.set_user_attr("objective_score", objective_score)

            return objective_score if self.preference_mode == "objective" else raw_score

        def callback(study, trial):
            config = trial.user_attrs["config"]
            raw_score = float(trial.user_attrs["raw_score"])
            config_key = tuple(sorted(config.items()))
            stat = stats_by_key.setdefault(config_key, RunningStat())
            stat.update(raw_score)

            if on_step is not None:
                ranked_keys = sorted(
                    stats_by_key.keys(),
                    key=lambda key: adjusted_mean(key) if self.preference_mode == "objective" else stats_by_key[key].mean,
                    reverse=True,
                )
                on_step(
                    {
                        "step": len(study.trials),
                        "total_steps": total_trials,
                        "epoch": (len(study.trials) - 1) // steps_per_epoch + 1,
                        "steps_per_epoch": steps_per_epoch,
                        "step_in_epoch": (len(study.trials) - 1) % steps_per_epoch + 1,
                        "total_evals": len(study.trials),
                        "candidate_results": [build_grouped_result(config_key)],
                        "top_results": [build_grouped_result(key) for key in ranked_keys[:target_top_k]],
                    }
                )

        study.optimize(objective, n_trials=total_trials, callbacks=[callback])

        ranked_keys = sorted(
            stats_by_key.keys(),
            key=lambda key: adjusted_mean(key) if self.preference_mode == "objective" else stats_by_key[key].mean,
            reverse=True,
        )
        return [build_grouped_result(key) for key in ranked_keys[:target_top_k]]


def create_optimizer(name: str = "bandit", **kwargs: Any) -> Any:
    if name == "bandit":
        return DiscreteBanditOptimizer(**kwargs)
    if name == "optuna":
        return OptunaOptimizer(**kwargs)
    raise ValueError(f"Unsupported optimizer name: {name}")


__all__ = [
    "DiscreteBanditOptimizer",
    "OptunaOptimizer",
    "RunningStat",
    "build_discrete_configs",
    "create_optimizer",
    "discrete_bandit_optimize",
]