import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.build_forecast_dataset import main


if __name__ == "__main__":
    main()
