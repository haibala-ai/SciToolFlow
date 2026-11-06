"""Run one named variant through the public baseline runner.

Example: python -m baselines.scimas.ablation.run --scimas-ablation wo-exp \
    --dataset mini --backend api --tasks all --output results/wo_exp/predictions.json
"""

import sys

from cli import main


if __name__ == "__main__":
    sys.argv[1:1] = ["run", "--baseline", "scimas"]
    main()
