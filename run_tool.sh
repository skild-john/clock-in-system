
---

# 📜 Here's your `run_tool.sh`:

```bash
#!/bin/bash

# Name of the conda environment
ENV_NAME="clock-in"

# Activate conda (adjust the path to your conda.sh if needed)
source ~/anaconda3/etc/profile.d/conda.sh

# Activate the environment
conda activate $ENV_NAME

# Run the script
python signin.py
