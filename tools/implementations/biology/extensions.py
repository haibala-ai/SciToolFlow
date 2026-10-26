import os
import hashlib
import io
import MDAnalysis
import numpy as np
from tools.runtime.config import Config

from Bio.Seq import Seq
from Bio.SeqUtils.ProtParam import ProteinAnalysis
from Bio.Blast import NCBIWWW, NCBIXML
## from MDAnalysis api
def analyze_atom_count(file_name: str) -> str:
    """
    Analyzes the number of atoms in a PDB file using MDAnalysis.

    Args:
        pdb_file (str): The path to the PDB file.

    Returns:
        str: A Markdown formatted string summarizing the atom count or an error message if the analysis fails.
    """
    try:
        pdb_file = os.path.join(Config().UPLOAD_FILES_BASE_PATH, file_name if file_name.endswith('.pdb') else file_name + '.pdb')
        u = MDAnalysis.Universe(pdb_file)
        atom_count = len(u.atoms)
        return f"## Atom Count Analysis\n\n- **PDB File**: `{file_name}`\n- **Total Atoms**: `{atom_count}`\n"
    except Exception as e:
        return f"Error occurred while analyzing atom count: {str(e)}\n"

def calculate_molecular_weight(file_name: str) -> str:
    """
    Sum MDAnalysis masses of the atoms actually parsed from an uploaded PDB.

    Args:
        file_name (str): Exact uploaded plain-PDB path or unique basename.
            A basename without .pdb receives that suffix. Public task assets
            and explicit current-task artifacts are also accepted.

    Returns:
        str: Legacy PDB File/Molecular Weight Markdown fields, plus source SHA256,
            parsed atom count, MDAnalysis version and the atom-inventory basis.
            Includes all topology atoms as parsed, including hetero atoms/water;
            no missing hydrogens/atoms are added, no occupancy weighting or
            protein-only selection is applied. This need not equal an intact
            sequence molar mass. Unknown/zero/nonfinite atomic masses fail.
    """
    try:
        from tools.implementations.general.research_data import _public_source_path

        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("file_name must identify an uploaded PDB file")
        name = file_name if file_name.lower().endswith('.pdb') else file_name + '.pdb'
        pdb_file = _public_source_path(name)
        raw = pdb_file.read_bytes()
        if not raw or len(raw) > 25 * 1024 * 1024:
            raise ValueError("PDB must be nonempty and at most25MiB")
        # Parse precisely the hashed bytes; a later file change cannot create a
        # mismatch between reported provenance and the atom inventory.
        u = MDAnalysis.Universe(io.StringIO(raw.decode('ascii')), format='PDB')
        weights = u.atoms.masses
        if len(weights) == 0 or not np.all(np.isfinite(weights)) or not np.all(weights > 0):
            raise ValueError("PDB has no parsed atoms or contains unknown/nonpositive/nonfinite atomic masses")
        molecular_weight = sum(weights)
        if not np.isfinite(molecular_weight):
            raise ValueError("Parsed atom-inventory mass is not finite")
        sha = hashlib.sha256(raw).hexdigest()
        return (f"## Molecular Weight Calculation\n\n- **PDB File**: `{file_name}`\n"
                f"- **Molecular Weight**: `{molecular_weight:.2f} g/mol`\n"
                f"- **Source SHA256**: `{sha}`\n"
                f"- **Parsed Atom Count**: `{len(weights)}`\n"
                f"- **MDAnalysis Version**: `{MDAnalysis.__version__}`\n"
                "- **Mass Basis**: Sum of as-parsed topology atomic masses, including hetero atoms/water; no added hydrogens, missing atoms, occupancy weighting or protein-only selection. This is not necessarily the intact sequence molar mass.\n")
    except Exception as e:
        return f"Error occurred while calculating molecular weight: {str(e)}\n"

def _pdb_inventory(file_name):
    """Parse the exact hashed PDB bytes once, retaining all topology atoms/first frame."""
    from tools.implementations.general.research_data import _public_source_path
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("file_name must identify an explicit plain PDB")
    name = file_name if file_name.lower().endswith('.pdb') else file_name + '.pdb'
    path = _public_source_path(name)
    raw = path.read_bytes()
    if not raw or len(raw) > 25 * 1024 * 1024:
        raise ValueError("PDB must be nonempty and at most25MiB")
    universe = MDAnalysis.Universe(io.StringIO(raw.decode('ascii')), format='PDB')
    if not len(universe.atoms) or not np.isfinite(universe.atoms.positions).all():
        raise ValueError("PDB requires parsed atoms and finite coordinates")
    return universe, {"source_sha256": hashlib.sha256(raw).hexdigest(),
                      "parsed_atom_count": len(universe.atoms), "coordinate_units": "angstrom",
                      "inventory": "all as-parsed topology atoms including hetero atoms/water; first frame; no added atoms"}


def calculate_center_of_mass(file_name: str) -> str:
    """Mass-weighted center of all as-parsed PDB topology atoms in the first frame, angstrom."""
    import json
    universe, provenance = _pdb_inventory(file_name)
    weights = universe.atoms.masses
    if not np.isfinite(weights).all() or not (weights > 0).all():
        raise ValueError("All as-parsed atomic masses must be positive and finite")
    center = np.average(universe.atoms.positions.astype(float), axis=0, weights=weights)
    if not np.isfinite(center).all():
        raise ValueError("Mass-weighted center must be finite")
    return json.dumps({**provenance, "center_of_mass": center.tolist(),
                       "mass_basis": "MDAnalysis topology atomic masses, no occupancy weighting",
                       "method": "sum(mass_i * coordinate_i)/sum(mass_i)"}, allow_nan=False)

def calculate_average_coordinates(file_name: str) -> str:
    """
    Calculates the average coordinates of all atoms in a PDB file using MDAnalysis.

    Args:
        pdb_file (str): The path to the PDB file.

    Returns:
        str: A Markdown formatted string with the average coordinates or an error message if the calculation fails.
    """
    try:
        pdb_file = os.path.join(Config().UPLOAD_FILES_BASE_PATH, file_name if file_name.endswith('.pdb') else file_name + '.pdb')
        u = MDAnalysis.Universe(pdb_file)
        average_coordinates = u.atoms.positions.mean(axis=0)
        return (f"## Average Coordinates Calculation\n\n"
                f"- **PDB File**: `{file_name}`\n"
                f"- **Average Coordinates**: `({average_coordinates[0]:.2f}, {average_coordinates[1]:.2f}, {average_coordinates[2]:.2f})`\n")
    except Exception as e:
        return f"Error occurred while calculating average coordinates: {str(e)}\n"

def calculate_atom_distance(file_name: str, atom_index_1: int = 0, atom_index_2: int = 1) -> str:
    """Euclidean distance of two zero-based parsed PDB topology atom indices, angstrom; no periodic wrapping."""
    import json
    if type(atom_index_1) is not int or type(atom_index_2) is not int or min(atom_index_1, atom_index_2) < 0:
        raise ValueError("Atom indices must be nonnegative integers")
    universe, provenance = _pdb_inventory(file_name)
    if max(atom_index_1, atom_index_2) >= len(universe.atoms):
        raise ValueError("Atom index exceeds the parsed topology inventory")
    atoms = universe.atoms[[atom_index_1, atom_index_2]]
    distance = float(np.linalg.norm(atoms.positions[0].astype(float) - atoms.positions[1].astype(float)))
    return json.dumps({**provenance, "atom_indices_zero_based": [atom_index_1, atom_index_2],
                       "atom_ids": [int(atom.id) for atom in atoms], "atom_names": list(atoms.names),
                       "distance_angstrom": distance, "periodic_boundary_conditions": False}, allow_nan=False)

## from Biopython


def get_amino_acid_frequency(sequence: str) -> str:
    """
    Calculates the frequency of each amino acid in a protein sequence.

    Args:
        sequence (str): The protein sequence.

    Returns:
        str: A Markdown formatted string summarizing the amino acid frequency.
    """
    try:
        # 计算氨基酸频率
        amino_acid_count = {}
        total_length = len(sequence)
        
        for amino_acid in sequence:
            if amino_acid in amino_acid_count:
                amino_acid_count[amino_acid] += 1
            else:
                amino_acid_count[amino_acid] = 1
        
        frequency_table = "| Amino Acid | Count | Frequency (%) |\n"
        frequency_table += "|-------------|-------|----------------|\n"
        
        for amino_acid, count in sorted(amino_acid_count.items()):
            frequency = (count / total_length) * 100
            frequency_table += f"| `{amino_acid}` | `{count}` | `{frequency:.2f}` |\n"

        return (f"## Amino Acid Frequency\n\n"
                f"- **Sequence**: `{sequence}`\n"
                f"- **Sequence Length (residues)**: `{total_length}`\n"
                f"- **Total Residues Counted**: `{sum(amino_acid_count.values())}`\n"
                f"{frequency_table}")
    except Exception as e:
        return f"Error occurred while calculating amino acid frequency: {str(e)}\n"


def get_reverse_complement(sequence: str) -> str:
    """
    Generates the reverse complement of a DNA sequence.

    Args:
        sequence (str): The DNA sequence.

    Returns:
        str: A Markdown formatted string with the reverse complement.
    """
    try:
        if not isinstance(sequence, str):
            raise ValueError("sequence must be a DNA string")
        sequence = ''.join(sequence.split()).upper()
        if not 1 <= len(sequence) <= 100000 or set(sequence) - set('ACGTRYSWKMBDHVN'):
            raise ValueError("Require1..100000IUPAC DNA bases; RNA, gaps, stops and headers unsupported")
        seq = Seq(sequence)
        reverse_complement = seq.reverse_complement()
        return (f"## Reverse Complement Sequence\n\n"
                f"- **Original Sequence**: `{sequence}`\n"
                f"- **Reverse Complement**: `{reverse_complement}`\n")
    except Exception as e:
        return f"Error occurred while generating reverse complement: {str(e)}\n"   


def _canonical_protein_sequence(sequence):
    if not isinstance(sequence, str):
        raise ValueError("sequence must be a string")
    normalized = ''.join(sequence.split()).upper()
    if not normalized or len(normalized) > 100000:
        raise ValueError("sequence must contain1..100000 canonical residues")
    invalid = sorted(set(normalized) - set('ACDEFGHIKLMNPQRSTVWY'))
    if invalid:
        raise ValueError("Noncanonical residues must be resolved by an explicit QC policy; not removed: " + ','.join(invalid))
    return normalized


def calculate_hydrophobicity_and_polarity(sequence: str) -> str:
    """
    Calculate GRAVY and estimated isoelectric point; pI is not molecular polarity.
    The public legacy tool name is retained for compatibility.

    Args:
        sequence (str): The protein sequence.

    Returns:
        str: Markdown GRAVY and estimated pI; no polarity or functional prediction.
    """
    try:
        sequence = _canonical_protein_sequence(sequence)
        
        analyzed_seq = ProteinAnalysis(sequence)
        hydropathy_index = analyzed_seq.gravy()  # Hydropathy index (GRAVY)
        isoelectric_point = analyzed_seq.isoelectric_point()

        return (f"## Hydropathy and Isoelectric Point\n\n"
                f"- **Sequence**: `{sequence}`\n"
                f"- **Hydropathy Index (GRAVY)**: `{hydropathy_index:.2f}`\n"
                f"- **Estimated Isoelectric Point (pI)**: `{isoelectric_point:.2f}`\n"
                "- pI is not molecular polarity; these are sequence descriptors, not measured function.\n")
    except Exception as e:
        return f"Error occurred while calculating hydrophobicity and polarity: {str(e)}\n"
    
def predict_secondary_structure(sequence: str) -> str:
    """
    Report composition-based helix/turn/sheet propensity fractions, not a fold prediction.
    Fractions count overlapping residue groups and need not sum to one.

    Args:
        sequence (str): The protein sequence.

    Returns:
        str: A Markdown formatted string summarizing the predicted secondary structure.
    """
    try:
        sequence = _canonical_protein_sequence(sequence)
        analyzed_seq = ProteinAnalysis(sequence)
        helix_fraction, turn_fraction, sheet_fraction = analyzed_seq.secondary_structure_fraction()
        
        return (f"## Residue Composition Propensity\n\n"
                f"- **Sequence**: `{sequence}`\n"
                f"- **Helix-prone Residue Fraction**: `{helix_fraction:.2%}`\n"
                f"- **Turn-prone Residue Fraction**: `{turn_fraction:.2%}`\n"
                f"- **Sheet-prone Residue Fraction**: `{sheet_fraction:.2%}`\n"
                "- Overlapping residue propensity groups; not predicted or observed secondary structure.\n")
    except Exception as e:
        return f"Error occurred while predicting secondary structure: {str(e)}\n"

def perform_blast_query(sequence_data: str, max_results: int = 20) -> str:
    """
    对给定的蛋白质序列使用 NCBI 的 BLAST 服务执行查询，并限制输出结果的数量。

    参数：
        sequence_data (str): 以 FASTA 格式提供的蛋白质序列字符串。
        max_results (int): 要输出的最大对齐结果数量，默认值为 20。

    返回：
        str: 包含 BLAST 查询结果的 Markdown 格式字符串或错误信息。
    """
    try:
        # Use the blastp program to query the nr (non-redundant protein) database
        result_handle = NCBIWWW.qblast("blastp", "nr", sequence_data)
        blast_record = NCBIXML.read(result_handle)
        
        markdown_output = "## BLAST Query Results\n\n"
        
        significant_alignments = False
        alignment_count = 0  # 添加计数器
        
        for alignment in blast_record.alignments:
            for hsp in alignment.hsps:
                if hsp.expect < 0.01:
                    significant_alignments = True
                    markdown_output += f"### Alignment\n\n"
                    markdown_output += f"- **Sequence**: `{alignment.title}`\n"
                    markdown_output += f"- **Length**: `{alignment.length}`\n"
                    markdown_output += f"- **E-value**: `{hsp.expect}`\n"
                    markdown_output += f"- **Query**: `{hsp.query[0:75]}...`\n"
                    markdown_output += f"- **Match**: `{hsp.match[0:75]}...`\n"
                    markdown_output += f"- **Subject**: `{hsp.sbjct[0:75]}...`\n\n"
                    
                    alignment_count += 1
                    if alignment_count >= max_results:
                        break  # 达到最大结果数量，退出循环
            if alignment_count >= max_results:
                break  # 达到最大结果数量，退出循环
        
        if not significant_alignments:
            markdown_output += "No significant alignments found.\n"
        
        return markdown_output
    except Exception as e:
        return f"Error occurred while performing BLAST query: {str(e)}\n"
    
# if __name__ == '__main__':
#     pdb_file = "/home/hjj/project/ToolsKG/DataFiles/pdb/esmfold/_temp.pdb"

#     res = analyze_atom_count(pdb_file)
#     # res = calculate_molecular_weight(pdb_file)
#     # res = calculate_center_of_mass(pdb_file)

#     # res = calculate_average_coordinates(pdb_file)
#     # res = calculate_atom_distance(pdb_file)
#     print(res)
