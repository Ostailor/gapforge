"""Built-in research skills."""

from gapforge.skills.cross_domain_analogy import CrossDomainAnalogy
from gapforge.skills.deep_reading import DeepReading
from gapforge.skills.deep_reading_llm import DeepReadingLLM
from gapforge.skills.experiment_designer import ExperimentDesigner
from gapforge.skills.gap_mining import GapMining
from gapforge.skills.gap_mining_llm import GapMiningLLM
from gapforge.skills.literature_cartographer import LiteratureCartographer
from gapforge.skills.novelty_gate import NoveltyGate
from gapforge.skills.novelty_gate_llm import NoveltyGateLLM
from gapforge.skills.paper_triage import PaperTriage
from gapforge.skills.reviewer_simulation import ReviewerSimulation

__all__ = [
    "CrossDomainAnalogy",
    "DeepReading",
    "DeepReadingLLM",
    "ExperimentDesigner",
    "GapMining",
    "GapMiningLLM",
    "LiteratureCartographer",
    "NoveltyGate",
    "NoveltyGateLLM",
    "PaperTriage",
    "ReviewerSimulation",
]
