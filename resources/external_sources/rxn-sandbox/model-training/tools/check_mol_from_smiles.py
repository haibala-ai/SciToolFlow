from rdkit import Chem, DataStructs
from rdkit.Chem.rdFingerprintGenerator import GetMorganGenerator


smiles = "O=S(=O)([O-])c1ccccc1~O=S(=O)([O-])c1ccccc1~O=S(=O)([O-])c1ccccc1~O=S(=O)([O-])c1ccccc1~O=S(=O)([O-])c1ccccc1~[Fe+2]~[Fe+2]~[Fe+2]~[Fe+2]~[Fe+2]~[Fe+2]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~[Fe+3]~"
    
if __name__ == "__main__":
    print(f"Smiles: {smiles}")
    mol1 = Chem.MolFromSmiles(smiles)
    print(f"Molecule: {mol1}")