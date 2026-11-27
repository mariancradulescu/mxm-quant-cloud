"""Earlier scope of the same read-only residual-source recovery mechanism."""
from pathlib import Path
from . import owner_held_residual_recovery as recovery
if __name__=='__main__':
 recovery.REGISTRY=Path('research/held_earlier_residual_recovery_2.json')
 recovery.main()
