import base64
import os
from rdkit import Chem
from rdkit.Chem.AtomPairs.Pairs import pyScorePair, ExplainPairScore
from rdkit.Chem.ChemUtils import SDFToCSV
from rdkit.Chem import Draw, rdMolDescriptors, DataStructs, rdMolDescriptors
from rdkit.Chem.EState import EState_VSA
from rdkit.ML.Cluster import Murtagh
from rdkit.Chem.Fingerprints.ClusterMols import ClusterPoints
from rdkit.Chem.Fraggle.FraggleSim import (
    GetFraggleSimilarity,
    generate_fraggle_fragmentation,
    isValidRingCut,
)

# from tools.utils import param_decorator, timer_decorator
from ..shared.common import param_decorator


@param_decorator
def explain_atom_pair_score(smiles, atom_idx1, atom_idx2):
    """
    Explain the pair score for a directly connected atom pair in a molecule.

    Args:
        molecule (str): SMILES representation of the molecule.
        atom_idx1 (int): Index of the first atom.
        atom_idx2 (int): Index of the second atom.

    Returns:
        str: A Markdown string explaining the pair score, or an error message.
    """
    try:
        # 检查输入类型
        if (
            not isinstance(smiles, str)
            or not isinstance(atom_idx1, int)
            or not isinstance(atom_idx2, int)
        ):
            raise ValueError("Invalid input types for molecule or atom indices.")

        # 将SMILES字符串转换为分子对象
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            raise ValueError("Invalid SMILES string.")

        # 检查原子索引是否在分子范围内
        if (
            atom_idx1 >= m.GetNumAtoms()
            or atom_idx2 >= m.GetNumAtoms()
            or atom_idx1 < 0
            or atom_idx2 < 0
        ):
            raise IndexError("Atom index out of range.")

        atom1 = m.GetAtomWithIdx(atom_idx1)
        atom2 = m.GetAtomWithIdx(atom_idx2)

        # 计算原子对的分数
        score = pyScorePair(atom1, atom2, dist=1)

        # 解释分数
        explanation = ExplainPairScore(score)

        # 生成Markdown格式的字符串
        markdown_output = f"""
### Pair Score Explanation

**Molecule:** `{smiles}`

**Atom Indices:** {atom_idx1} and {atom_idx2}

**Score:** {score}

**Explanation:**
- **First Atom:** `{explanation[0]}`
- **Second Atom:** `{explanation[2]}`
- **Distance:** `{explanation[1]}` (This is typically the bond distance in the molecule)
"""
    except Exception as e:
        # 发生异常时返回错误消息
        markdown_output = f"An error occurred: {e}"

    return markdown_output


# 输出中的数字：每个数字代表在位向量中被设置为 1 的位置。
# 这些位置对应于分子中特定的原子对配置。换句话说，这些数字是用于唯一标识分子中原子对的编码。
# 例如，数字 541732 表示分子中的一个特定原子对，其特定的空间排列和化学性质使得这个位置在位向量中被设置为 1。
def get_atom_pair_fingerprint_as_bit_vect(smiles):
    'GetAtomPairFingerprintAsBitVect retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetAtomPairFingerprintAsBitVect retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def assign_patty_types(smiles: str) -> dict:
    'Return zero-based indexed patty values from the RDKit hydrogen-suppressed parsed graph. Raw RDKit feature-vector positions are preserved rather than assigned guessed chemical labels. Full finite values are returned as JSON; invalid structures raise errors.'
    from .molecular_operations import atom_properties
    return atom_properties(smiles, 'patty')


# include_chirality 手性信息
def explain_atom_code(smiles, atom_idx, include_chirality=True):
    'ExplainAtomCode retired: One atom-code kernel exposes selected/all atoms and explicit chirality. Use AtomPairCodes. See the catalog migration feedback for explicit arguments.'
    raise ValueError('ExplainAtomCode retired: One atom-code kernel exposes selected/all atoms and explicit chirality. Use AtomPairCodes. See the catalog migration feedback for explicit arguments.')


def test_molecule(smiles):
    """
    Perform a series of tests on a molecule, including sanitization, removal of hydrogens,
    and canonicalization check. This function helps in validating the molecule's structure
    and consistency.

    Args:
        smiles (str): SMILES representation of the molecule.

    Returns:
        str: A string summarizing the test results. Returns 'Valid and consistent molecule structure.'
        if tests are passed, otherwise provides an error code indicating the type of issue encountered.
    """
    try:
        # 检查输入类型
        if not isinstance(smiles, str):
            raise ValueError("Input must be a SMILES string.")

        # 将SMILES字符串转换为分子对象
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return "Error: Invalid SMILES string."

        # 对分子进行测试
        reference = Chem.MolToSmiles(mol, canonical=True)
        reordered = Chem.RenumberAtoms(mol, list(reversed(range(mol.GetNumAtoms()))))
        result_code = (
            0 if reference == Chem.MolToSmiles(reordered, canonical=True) else -3
        )
        if result_code == 0:
            return "Valid and consistent molecule structure."
        elif result_code == -1:
            return "Error: Molecule failed during sanitization."
        elif result_code == -2:
            return "Error: Exception occurred during processing."
        elif result_code == -3:
            return "Error: Molecule failed during canonicalization check."
        else:
            return f"Error: Unknown issue encountered. Error code: {result_code}"
    except Exception as e:
        # 发生异常时返回错误消息
        return f"Error occurred during molecule testing: {e}"


def convert_sdf_to_csv(sdf_file):
    """
    Convert a single SDF file to a CSV file and provide a download link.

    Args:
        sdf_file (str): Path to the SDF file.

    Returns:
        str: A Markdown string with a link to the converted CSV file, or an error message.
    """
    try:
        # 检查输入类型
        if not isinstance(sdf_file, str):
            raise ValueError("Input must be a file path.")

        # 检查文件是否存在
        if not os.path.exists(sdf_file):
            raise FileNotFoundError(f"No SDF file found at {sdf_file}")

        download_folder = os.path.dirname(os.path.abspath(sdf_file))
        csv_filename = os.path.basename(sdf_file).replace(".sdf", ".csv")
        csv_file_path = os.path.join(download_folder, csv_filename)

        # 使用 RDKit 分子供应器读取 SDF 文件
        suppl = Chem.SDMolSupplier(sdf_file)
        if not suppl:
            raise ValueError("Failed to read SDF file.")

        # 打开 CSV 文件以进行写入
        with open(csv_file_path, "w", newline="") as csv_file:
            SDFToCSV.Convert(suppl, csv_file)

        # 使用服务器IP地址和文件名构建下载链接
        download_link = csv_file_path

        markdown_output = (
            f"### Converted CSV File\n\n- [{csv_filename}]({download_link})\n"
        )
    except Exception as e:
        # 发生异常时返回错误消息
        markdown_output = f"An error occurred during conversion: {e}"

    return markdown_output


def show_mol(smiles):
    """
    Generate a molecule image from its SMILES representation and embed it directly in Markdown.

    Args:
        smiles (str): A SMILES representation of the molecule to be displayed.

    Returns:
        str: A Markdown string with embedded molecule image, or an error message.
    """
    useSVG = True
    try:
        # 检查输入类型
        if not isinstance(smiles, str):
            raise ValueError("SMILES must be a string.")

        # 将SMILES字符串转换为分子对象
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")

        markdown_output = f"### Molecule Information\n\n**SMILES:** `{smiles}`\n\n"

        # 生成分子图像
        if useSVG:
            svg = Draw.MolsToGridImage([mol], useSVG=useSVG, subImgSize=(300, 300)).data
            svg_base64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
            markdown_output += (
                f"![Molecule Image](data:image/svg+xml;base64,{svg_base64})"
            )
        else:
            img = Draw.MolToImage(mol, size=(300, 300))
            temp_img_path = "temp_img.png"
            img.save(temp_img_path)
            with open(temp_img_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode("utf-8")
            markdown_output += f"![Molecule Image](data:image/png;base64,{img_base64})"
            os.remove(temp_img_path)

        return markdown_output
    except Exception as e:
        # 发生异常时返回错误消息
        return f"An error occurred while generating molecule image: {e}"


def type_atoms_in_molecule(smiles):
    'TypeAtomsInMolecule retired: One EState analysis shares atom typing/indices and type aggregation. Use EStateAnalysis. See the catalog migration feedback for explicit arguments.'
    raise ValueError('TypeAtomsInMolecule retired: One EState analysis shares atom typing/indices and type aggregation. Use EStateAnalysis. See the catalog migration feedback for explicit arguments.')


def calculate_estate_indices(smiles):
    'CalculateEstateIndices retired: One EState analysis shares atom typing/indices and type aggregation. Use EStateAnalysis. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CalculateEstateIndices retired: One EState analysis shares atom typing/indices and type aggregation. Use EStateAnalysis. See the catalog migration feedback for explicit arguments.')


def calculate_estate_vsa(smiles):
    """
    Calculate EState VSA indices for a molecule based on its SMILES representation.

    Args:
        smiles (str): A SMILES representation of the molecule.

    Returns:
        str: A Markdown formatted string describing the EState VSA indices of the molecule, or an error message.
    """
    try:
        # 检查输入类型
        if not isinstance(smiles, str):
            raise ValueError("Input must be a SMILES string.")

        # 将SMILES字符串转换为分子对象
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")

        vsa_functions = [
            EState_VSA.EState_VSA1,
            EState_VSA.EState_VSA2,
            EState_VSA.EState_VSA3,
            EState_VSA.EState_VSA4,
            EState_VSA.EState_VSA5,
            EState_VSA.EState_VSA6,
            EState_VSA.EState_VSA7,
            EState_VSA.EState_VSA8,
            EState_VSA.EState_VSA9,
            EState_VSA.EState_VSA10,
            EState_VSA.EState_VSA11,
        ]

        # 计算EState VSA指数
        vsa_indices = [func(mol) for func in vsa_functions]

        # 格式化输出
        markdown_output = f"### EState VSA Indices for Molecule: `{smiles}`\n\n"
        for i, index in enumerate(vsa_indices):
            markdown_output += f"- VSA Index {i + 1}: {index:.4f}\n"

        return markdown_output
    except Exception as e:
        # 发生异常时返回错误消息
        return f"An error occurred while calculating EState VSA indices: {e}"


def generate_estate_fingerprint(smiles):
    'GenerateEstateFingerprint retired: One EState analysis shares atom typing/indices and type aggregation. Use EStateAnalysis. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GenerateEstateFingerprint retired: One EState analysis shares atom typing/indices and type aggregation. Use EStateAnalysis. See the catalog migration feedback for explicit arguments.')


def extract_rotatable_dihedrals_from_sdf(sdffile):
    """
    Extract rotatable dihedrals from a molecule in an SDF file.

    Args:
        sdffile (str): The file path of the SDF file containing the molecule.

    Returns:
        str: A Markdown formatted string listing the indices of atoms forming each
             rotatable dihedral in the molecule, or an error message.
    """
    try:
        # 检查输入类型
        if not isinstance(sdffile, str):
            raise ValueError("Input must be a file path.")

        # 读取SDF文件
        mols_suppl = Chem.SDMolSupplier(sdffile)
        if not mols_suppl or len(mols_suppl) == 0:
            raise ValueError("No molecules found in the SDF file.")

        mol = mols_suppl[0]  # 取第一个分子
        if mol is None:
            raise ValueError("Invalid molecule in the SDF file.")

        def getdihes(mol):
            dihes = []
            for bond in mol.GetBonds():
                if bond.GetBondType().name == "SINGLE" and not bond.IsInRing():
                    atom2id = bond.GetBeginAtomIdx()
                    atom3id = bond.GetEndAtomIdx()
                    atom2 = bond.GetBeginAtom()
                    atom3 = bond.GetEndAtom()

                    if len(atom3.GetNeighbors()) == 1 or len(atom2.GetNeighbors()) == 1:
                        continue
                    else:
                        atom1s = [
                            at.GetIdx()
                            for at in atom2.GetNeighbors()
                            if at.GetIdx() != atom3id
                        ]
                        atom4s = [
                            at.GetIdx()
                            for at in atom3.GetNeighbors()
                            if at.GetIdx() != atom2id
                        ]

                        if atom1s and atom4s:
                            dihes.append([atom1s[0], atom2id, atom3id, atom4s[0]])
            return dihes

        dihedrals = getdihes(mol)

        markdown_output = "### Rotatable Dihedrals in Molecule\n\n"
        markdown_output += "Extracted from file: `{}`\n\n".format(sdffile)
        for i, dihedral in enumerate(dihedrals):
            markdown_output += f"- Dihedral {i+1}: Atoms {dihedral[0]}, {dihedral[1]}, {dihedral[2]}, {dihedral[3]}\n"

        return markdown_output
    except Exception as e:
        # 发生异常时返回错误消息
        return f"An error occurred while extracting rotatable dihedrals: {e}"


def calculate_molecular_center(sdffile):
    'CalculateMolecularCenter retired: One geometric-centroid core handles coordinate-format adapters with explicit inventory. Use MolecularCentroid. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CalculateMolecularCenter retired: One geometric-centroid core handles coordinate-format adapters with explicit inventory. Use MolecularCentroid. See the catalog migration feedback for explicit arguments.')


def calculate_fsp3(smiles):
    """
    Calculate the fraction of SP3 hybridized carbons (FSP3) for a given molecule.

    Args:
        smiles (str): A SMILES representation of the molecule.

    Returns:
        str: A Markdown formatted string describing the FSP3 value of the molecule, or an error message.
    """
    try:
        # 检查输入类型
        if not isinstance(smiles, str):
            raise ValueError("Input must be a SMILES string.")

        # 将SMILES字符串转换为分子对象
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")

        # 计算 FSP3
        FSP3 = rdMolDescriptors.CalcFractionCSP3(mol)

        markdown_output = f"### FSP3 Descriptor for Molecule: `{smiles}`\n\n"
        markdown_output += f"- FSP3 (Fraction of SP3 hybridized carbons): {FSP3:.3f}\n"

        return markdown_output
    except Exception as e:
        # 发生异常时返回错误消息
        return f"An error occurred while calculating FSP3: {e}"


def calculate_usrcat_scores(sdffile):
    'CalculateUsrcatScores retired: One USRCAT comparison core preserves source/conformer policies; Morgan comparison is a separate method. Use CompareMolecularShapes, CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CalculateUsrcatScores retired: One USRCAT comparison core preserves source/conformer policies; Morgan comparison is a separate method. Use CompareMolecularShapes, CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.')


def calculate_shape_similarity(smiles_list):
    'CalculateShapeSimilarity retired: One USRCAT comparison core preserves source/conformer policies; Morgan comparison is a separate method. Use CompareMolecularShapes, CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CalculateShapeSimilarity retired: One USRCAT comparison core preserves source/conformer policies; Morgan comparison is a separate method. Use CompareMolecularShapes, CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.')


def calculate_pmi(smiles):
    'CalculatePmi retired: One NPR1/NPR2 core exposes geometry and optimization policy explicitly. Use NormalizedPrincipalMoments. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CalculatePmi retired: One NPR1/NPR2 core exposes geometry and optimization policy explicitly. Use NormalizedPrincipalMoments. See the catalog migration feedback for explicit arguments.')


def calculate_distance_matrix(smiles_list):
    'CalculateDistanceMatrix retired: Pair and matrix similarity/distance share one fingerprint comparison kernel. Use CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CalculateDistanceMatrix retired: Pair and matrix similarity/distance share one fingerprint comparison kernel. Use CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.')


def tanimoto_similarity(fp1, fp2):
    return DataStructs.TanimotoSimilarity(fp1, fp2)


def cluster_molecules(smiles_list, metric=tanimoto_similarity, algorithm_id=Murtagh.WARDS):
    'ClusterMolecules retired: Old clustering confused similarity/distance callbacks and leaf indices with clusters. Use ClusterMolecularFingerprints. See the catalog migration feedback for explicit arguments.'
    raise ValueError('ClusterMolecules retired: Old clustering confused similarity/distance callbacks and leaf indices with clusters. Use ClusterMolecularFingerprints. See the catalog migration feedback for explicit arguments.')


# 未实现
def cluster_molecules_from_details(details):
    """
    Clusters molecules based on the provided details and returns the clustering results in Markdown format.

    Args:
        details (SimpleDetails): An object containing data, metric, and cluster algorithm.

    Returns:
        str: A Markdown formatted string representing the clustering results, including the number of clusters.
    """
    # 检查是否有足够的数据
    if not details.data:
        return "### Clustering Results\n\nNo data available for clustering."

    # 使用ClusterPoints函数进行聚类
    clust_tree = ClusterPoints(details.data, details.metric, details.cluster_algo)

    # 分析聚类结果
    num_clusters = len(set([pt.GetIndex() for pt in clust_tree.GetPoints()]))

    # 格式化聚类结果为Markdown
    markdown_output = "### Clustering Results\n\n"
    markdown_output += f"Total number of clusters: {num_clusters}\n\n"
    for pt in clust_tree.GetPoints():
        idx = pt.GetIndex() - 1
        label = details.data[idx][0]  # 获取分子的SMILES字符串
        markdown_output += f"- {label}: Cluster Index = {idx}\n"

    return markdown_output


def process_fingerprint_mol(smiles):
    'ProcessFingerprintMol retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('ProcessFingerprintMol retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def fingerprints_from_smiles(smiles_list):
    'FingerprintsFromSmiles retired: Use MolecularFingerprint with one smiles or explicit csv_file/columns and the legacy RDKit path preset. See catalog migration feedback for exact options.'
    raise ValueError('FingerprintsFromSmiles retired: Use MolecularFingerprint with one smiles or explicit csv_file/columns and the legacy RDKit path preset. See catalog migration feedback for exact options.')


def fold_fingerprint_from_smiles(smiles, tgtDensity=0.3, minSize=64):
    'FoldFingerprintFromSmiles retired: Density folding is an explicit path-fingerprint parameter, not a second algorithm. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('FoldFingerprintFromSmiles retired: Density folding is an explicit path-fingerprint parameter, not a second algorithm. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def get_rdk_fingerprint_from_smiles(smiles):
    'GetRdkFingerprintFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetRdkFingerprintFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


@param_decorator
def get_fraggle_similarity(smiles1, smiles2, tverskyThresh=0.8):
    """
    Calculate the Fraggle similarity between two molecules represented by SMILES strings.

    Args:
        smiles1 (str): The SMILES string of the first molecule (query molecule).
        smiles2 (str): The SMILES string of the second molecule (reference molecule).
        tverskyThresh (float, optional): Tversky threshold for similarity. Defaults to 0.8.

    Returns:
        str: A Markdown formatted string representing the Fraggle similarity and the matching substructure.
    """
    try:
        # Generate molecules from SMILES
        queryMol = Chem.MolFromSmiles(smiles1)
        refMol = Chem.MolFromSmiles(smiles2)

        if not queryMol or not refMol:
            return "Invalid SMILES string(s)."

        # Calculate Fraggle similarity
        sim, match = GetFraggleSimilarity(queryMol, refMol, tverskyThresh)

        # Formatting the output in Markdown
        markdown_output = "### Fraggle Similarity\n\n"
        markdown_output += f"**SMILES 1:** `{smiles1}`\n"
        markdown_output += f"**SMILES 2:** `{smiles2}`\n\n"
        markdown_output += f"**Similarity Score:** `{sim}`\n"
        markdown_output += f"**Matching Substructure:** `{match}`\n"

        return markdown_output
    except Exception as e:
        # In case of an error
        return f"An error occurred: {e}"


def generate_fraggle_fragments(smiles):
    """
    Generate all possible Fraggle fragmentations for a molecule represented by a SMILES string.

    Args:
        smiles (str): The SMILES string of the molecule.

    Returns:
        str: A Markdown formatted string representing the list of possible fragmentations.
    """
    try:
        # Generate molecule from SMILES
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return "Invalid SMILES string."

        # Generate Fraggle fragmentations
        fragments = generate_fraggle_fragmentation(mol)

        # Sorting and formatting the fragments
        sorted_fragments = sorted([".".join(sorted(s.split("."))) for s in fragments])

        # Formatting the output in Markdown
        markdown_output = "### Fraggle Fragmentations\n\n"
        markdown_output += f"**SMILES:** `{smiles}`\n\n"
        markdown_output += "**Fragments:**\n"
        for fragment in sorted_fragments:
            markdown_output += f"- `{fragment}`\n"

        return markdown_output
    except Exception as e:
        # In case of an error
        return f"An error occurred: {e}"


def check_valid_ring_cut(smiles):
    """
    Check if the molecule represented by a SMILES string is a valid ring cut.

    Args:
        smiles (str): The SMILES string of the molecule.

    Returns:
        str: A message indicating whether the molecule is a valid ring cut or not.
    """
    try:
        # Generate molecule from SMILES
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return "Invalid SMILES string."

        # Check for valid ring cut
        is_valid = isValidRingCut(mol)

        return "Valid ring cut." if is_valid else "Not a valid ring cut."
    except Exception as e:
        # In case of an error
        return f"An error occurred: {e}"


def build_atom_pair_fp_from_smiles(smiles):
    'BuildAtomPairFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('BuildAtomPairFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def build_torsions_fp_from_smiles(smiles):
    'BuildTorsionsFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('BuildTorsionsFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def build_rdkit_fp_from_smiles(smiles):
    'BuildRdkitFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('BuildRdkitFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


# 未实现
def build_pharm2d_fp_from_smiles(smiles, fdef_file=None):
    'BuildPharm2DFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('BuildPharm2DFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


# 'UIntSparseIntVect' object has no attribute 'ToBitString'
def build_morgan_fp_from_smiles(smiles):
    'BuildMorganFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('BuildMorganFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def build_avalon_fp_from_smiles(smiles):
    'BuildAvalonFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('BuildAvalonFpFromSmiles retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def convert_smiles_to_inchi(smiles):
    'ConvertSmilesToInchi retired: Duplicate standard-InChI conversion has one canonical entry. Use SMILESToInChI. See the catalog migration feedback for explicit arguments.'
    raise ValueError('ConvertSmilesToInchi retired: Duplicate standard-InChI conversion has one canonical entry. Use SMILESToInChI. See the catalog migration feedback for explicit arguments.')


def generate_mol_key_from_smiles(smiles):
    'GenerateMolKeyFromSmiles retired: One MolKey construction returns its key and stereo code with error state. Use MolecularKey. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GenerateMolKeyFromSmiles retired: One MolKey construction returns its key and stereo code with error state. Use MolecularKey. See the catalog migration feedback for explicit arguments.')


def get_stereo_code_from_smiles(smiles):
    'GetStereoCodeFromSmiles retired: One MolKey construction returns its key and stereo code with error state. Use MolecularKey. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetStereoCodeFromSmiles retired: One MolKey construction returns its key and stereo code with error state. Use MolecularKey. See the catalog migration feedback for explicit arguments.')
