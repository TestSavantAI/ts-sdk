from dataclasses import dataclass
import importlib
from itertools import product
from math import ceil, sqrt
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


PreferenceOption = Tuple[Any, float]
SearchSpace = Dict[str, Sequence[PreferenceOption]]
ConfigDict = Dict[str, Any]


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


class OptunaOptimizer:
    """Config optimizer backed by Optuna when it is available."""

    def __init__(
        self,
        top_k: int = 10,
        seed: int = 42,
        exploration_ratio: float = 0.5,
        min_exploration_trials: int = 8,
        preference_strength: float = 0.02,
        preference_mode: str = "objective",
    ) -> None:
        self.top_k = top_k
        self.seed = seed
        self.exploration_ratio = exploration_ratio
        self.min_exploration_trials = min_exploration_trials
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
        should_stop: Optional[Callable[[Dict[str, Any]], bool]] = None,
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
        if not 0.0 < self.exploration_ratio <= 1.0:
            raise ValueError("exploration_ratio must be in the interval (0, 1].")
        if self.min_exploration_trials < 1:
            raise ValueError("min_exploration_trials must be at least 1.")

        optuna_logging = getattr(optuna, "logging", None)
        previous_verbosity = None
        if (
            optuna_logging is not None
            and hasattr(optuna_logging, "WARNING")
            and hasattr(optuna_logging, "set_verbosity")
            and hasattr(optuna_logging, "get_verbosity")
        ):
            previous_verbosity = optuna_logging.get_verbosity()
            optuna_logging.set_verbosity(optuna_logging.WARNING)

        configs, preferences = build_discrete_configs(search_space)
        config_index = {tuple(sorted(config.items())): index for index, config in enumerate(configs)}
        target_top_k = self.top_k if top_k is None else top_k
        total_trials = epochs * steps_per_epoch
        exploration_trials = min(
            total_trials,
            len(configs),
            max(self.min_exploration_trials, int(ceil(total_trials * self.exploration_ratio))),
        )
        exploration_configs = list(configs)
        random.Random(self.seed).shuffle(exploration_configs)
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

        try:
            sampler = optuna.samplers.TPESampler(seed=self.seed, n_startup_trials=0)
        except TypeError:
            sampler = optuna.samplers.TPESampler(seed=self.seed)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        option_values = {key: [value for value, _ in options] for key, options in search_space.items()}

        def objective(trial):
            batch = sample_batch_fn() if sample_batch_fn is not None else None
            if trial.number < exploration_trials:
                config = dict(exploration_configs[trial.number])
            else:
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

            if on_step is not None or should_stop is not None:
                ranked_keys = sorted(
                    stats_by_key.keys(),
                    key=lambda key: adjusted_mean(key) if self.preference_mode == "objective" else stats_by_key[key].mean,
                    reverse=True,
                )
                step_payload = {
                    "step": len(study.trials),
                    "total_steps": total_trials,
                    "epoch": (len(study.trials) - 1) // steps_per_epoch + 1,
                    "steps_per_epoch": steps_per_epoch,
                    "step_in_epoch": (len(study.trials) - 1) % steps_per_epoch + 1,
                    "total_evals": len(study.trials),
                    "candidate_results": [build_grouped_result(config_key)],
                    "top_results": [build_grouped_result(key) for key in ranked_keys[:target_top_k]],
                }

                if on_step is not None:
                    on_step(step_payload)

                if should_stop is not None and should_stop(step_payload):
                    study.stop()

        try:
            study.optimize(objective, n_trials=total_trials, callbacks=[callback])
        finally:
            if previous_verbosity is not None:
                optuna_logging.set_verbosity(previous_verbosity)

        ranked_keys = sorted(
            stats_by_key.keys(),
            key=lambda key: adjusted_mean(key) if self.preference_mode == "objective" else stats_by_key[key].mean,
            reverse=True,
        )
        return [build_grouped_result(key) for key in ranked_keys[:target_top_k]]


def create_optimizer(name: str = "optuna", **kwargs: Any) -> Any:
    if name == "optuna":
        return OptunaOptimizer(**kwargs)
    raise ValueError(f"Unsupported optimizer name: {name}")


__all__ = [
    "OptunaOptimizer",
    "RunningStat",
    "build_discrete_configs",
    "create_optimizer",
]