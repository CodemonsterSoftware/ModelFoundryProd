import abc
from typing import Dict, Any, Optional
from pathlib import Path

class ExecutionEngine(abc.ABC):
    """
    Base class for all Forge module execution backends.
    """
    
    @abc.abstractmethod
    def run_task(self, job_meta: Dict[str, Any], input_path: Optional[str], output_dir: str) -> Dict[str, Any]:
        """
        Execute the task.
        
        Args:
            job_meta: Dictionary containing job configuration and parameters.
            input_path: Path to the input file (e.g. STL). Can be None for generators.
            output_dir: Directory where output files should be written.
            
        Returns:
            A dictionary of updates to merge into the job_meta (e.g. status, parts, warnings).
        """
        pass
