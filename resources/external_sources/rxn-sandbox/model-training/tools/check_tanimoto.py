from rdkit import Chem, DataStructs
from rdkit.Chem.rdFingerprintGenerator import GetMorganGenerator


predicted_texts = [
    "",
]

target_texts = [
    "",
]


if __name__ == "__main__":
    similarities = []
    invalid_pairs = 0
    generator = GetMorganGenerator(radius=2, fpSize=2048)
    for pred, tgt in zip(predicted_texts, target_texts):
        
        # Get molecule from prediction
        print(f"Predicted smiles (pred): {pred}")
        mol1 = Chem.MolFromSmiles(pred)
        print(f"Predicted molecule (mol1): {mol1}")

        # Get molecule from ground truth
        print(f"Target smiles (tgt): {tgt}")
        mol2 = Chem.MolFromSmiles(tgt)
        print(f"Target molecule (mol2): {mol2}")
        
        # Increment invalid pairs on failure
        if mol1 is None or mol2 is None:
            invalid_pairs += 1
            print(f"Invalid pair! Total: {invalid_pairs}")
            continue


        fp1 = generator.GetFingerprint(mol1)
        print(f"Predicted fingerprint (fp1): {fp1}")
        fp2 = generator.GetFingerprint(mol2)
        print(f"Target fingerprint (fp2): {fp2}")
        sim = DataStructs.TanimotoSimilarity(fp1, fp2)
        print(f"Similarity (sim): {sim}")
        similarities.append(sim)

    avg_tanimoto = sum(similarities) / len(similarities) if len(similarities) > 0 else 0
    print(f"Average Tanimoto (avg_tanimoto): {avg_tanimoto}")
