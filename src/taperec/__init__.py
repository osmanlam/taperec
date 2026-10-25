"""taperec — VCR for LLM agent traffic. Record once. Replay forever. Pay nothing."""

from .recorder import Taperec, TaperecError, new_episodes, record, replay

__version__ = "0.1.0"
__all__ = ["Taperec", "TaperecError", "record", "replay", "new_episodes", "__version__"]
