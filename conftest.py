import sys
from pathlib import Path

# Add project root to path so 'scripts' package is importable in tests
sys.path.insert(0, str(Path(__file__).parent))
