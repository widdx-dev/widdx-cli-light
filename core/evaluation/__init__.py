"""Evaluation framework — benchmarks, truth, replay, product verification."""
from .framework import EvaluationRunner, TaskResult, TaskCorpus, get_evaluation_runner  # noqa: F401
from .truth import ExperimentalTruthLayer, get_truth  # noqa: F401
from .replay import ReplayEngine, get_replay_engine  # noqa: F401
from .swebench import SWEBenchRunner, get_swe_runner  # noqa: F401
