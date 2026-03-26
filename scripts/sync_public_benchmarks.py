import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from app.forecast_support import sync_public_benchmarks


if __name__ == "__main__":
    print(json.dumps(sync_public_benchmarks(), indent=2))
