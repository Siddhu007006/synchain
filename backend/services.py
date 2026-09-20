from agents import DecisionAgent
from schemas import SimulationInput, SimulationResult

_decision_agent = DecisionAgent()


def simulate_supply_chain(data: SimulationInput) -> SimulationResult:
    """Delegate to the multi-agent decision pipeline."""
    return _decision_agent.run(payload=data)
