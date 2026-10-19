import pandas as pd
import os
import json

# Define base paths
base_path = "data/pistachio"
data_path = os.path.join(base_path, "pipeline")

# Define input CSV files
csv_files = {
    "train": os.path.join(data_path, "data.processed.train.csv"),
    "test": os.path.join(data_path, "data.processed.test.csv"),
    "validation": os.path.join(data_path, "data.processed.validation.csv")
}

# Define output directories
forward_dir = os.path.join(base_path, "data.forward")
retro_dir = os.path.join(base_path, "data.retro")
os.makedirs(forward_dir, exist_ok=True)
os.makedirs(retro_dir, exist_ok=True)

# Process each dataset
for split, csv_file in csv_files.items():
    # Read CSV file
    df = pd.read_csv(csv_file, header=0, names=["reactants", "products"], sep=">>", engine="python")

    # Escape backslashes
    df["reactants"] = df["reactants"].astype(str)
    df["products"] = df["products"].astype(str)

    # Write forward JSONL
    forward_file = os.path.join(forward_dir, f"{split}.jsonl")
    with open(forward_file, "w") as f_out:
        for _, row in df.iterrows():
            json.dump({"source": row["reactants"], "target": row["products"]}, f_out)
            f_out.write("\n")

    # Write retro JSONL
    retro_file = os.path.join(retro_dir, f"{split}.jsonl")
    with open(retro_file, "w") as f_out:
        for _, row in df.iterrows():
            json.dump({"source": row["products"], "target": row["reactants"]}, f_out)
            f_out.write("\n")

print("All JSONL files created successfully.")

