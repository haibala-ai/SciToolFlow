from src.utils.paths import local_root, artifacts_root
import subprocess
import pandas as pd
import json
import re
import os
import requests
from pathlib import Path
from tools.runtime.config import Config
from tools.implementations.shared.http_retry import request_with_retries



code_dir="TempFiles/pdb/code_protein"
# model, tokenizer = ForceGPTmodel(model_name=Config().FORCEGPT_MODEL_PATH, device=device)

def _load_force_dependencies():
    global device, ForceGPTmodel, extract_start_and_end, generate_output_from_prompt, extract_task
    import torch
    torch.set_num_threads(int(os.getenv("SCITOOL_MODEL_CPU_THREADS", "4")))
    device = torch.device("cpu")
    from tools.implementations.biology.force_gpt import ForceGPTmodel
    from tools.implementations.biology.support.utils import extract_start_and_end, generate_output_from_prompt, extract_task


def _load_chroma_dependencies():
    global torch, Chroma, conditioners, Protein, graph_classifier, procap
    import torch
    torch.set_num_threads(int(os.getenv("SCITOOL_MODEL_CPU_THREADS", "4")))
    from chroma import Chroma, conditioners, Protein, api
    from chroma.models import graph_classifier, procap
    # Keep the credential in the user's private configuration, rather than
    # writing Chroma's default config.json into the package directory.
    api.read_key = lambda key_directory=None: Config().CHROMA_KEY
    from tools.implementations.shared.chroma_weights import download_from_generate
    api.download_from_generate = download_from_generate


def analyze_protein_CATH_from_PDBID(PDB_id: str) -> str:
    """
    Queries the CATH database for a given PDB ID and returns the CATH classification
    along with a detailed explanation in an easy-to-understand Markdown format.

    Args:
        PDB_id (str): The PDB ID of the protein to query.

    Returns:
        str: A Markdown formatted string that describes the CATH classification of the protein
             with detailed explanations. If an error occurs or the PDB ID is not found,
             an error message is returned.
    """
    try:
        if not re.fullmatch(r"[0-9][a-zA-Z0-9]{3}", PDB_id):
            raise ValueError("Expected a four-character PDB identifier")
        with requests.Session() as session:
            session.trust_env = False
            response = request_with_retries(session, "GET", f"https://www.ebi.ac.uk/pdbe/api/mappings/cath/{PDB_id.lower()}", timeout=20)
        response.raise_for_status()
        classifications = response.json()[PDB_id.lower()].get("CATH", {})
        if not classifications:
            raise ValueError(f"No CATH classification found for PDB ID '{PDB_id}'.")
        # Preserve all domains and names from the provider, including mixed classes.
        markdown_output = json.dumps({"pdb_id": PDB_id, "source": "PDBe CATH mappings", "classifications": classifications})
    except Exception as e:
        markdown_output = f"Error occurred while querying CATH classification: {str(e)}\n"

    return markdown_output

def _local_pdb(name):
    """Resolve explicit task/upload coordinates, or fetch a fresh PDB record.

    Shared unversioned upload-directory caches are not consulted implicitly.
    Reuse an explicit FetchPDBCoordinateFile artifact across analyses instead.
    """
    from tools.implementations.general.research_data import _public_source_path
    from tools.implementations.biology.protein_records import fetch_pdb_coordinate_file
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Require a coordinate file or bare PDB identifier")
    filename = name if name.lower().endswith('.pdb') else name + '.pdb'
    try:
        return str(_public_source_path(filename))
    except (PermissionError, FileNotFoundError):
        identifier = name[:-4] if name.lower().endswith('.pdb') else name
        if not re.fullmatch(r"[0-9][A-Za-z0-9]{3}", identifier):
            raise
        return fetch_pdb_coordinate_file(identifier)["pdb_path"]


def analyze_protein_length_from_PDB(PDB_name: str, chain: str = "") -> str:
    """Count amino-acid residues in an uploaded PDB or a PDB ID fetched from RCSB.

    ``chain`` is optional: when given, only that chain is counted and the per-chain
    value is reported next to the entry-wide total.
    """
    from Bio.PDB import PDBParser, is_aa
    path = _local_pdb(PDB_name)
    structure = PDBParser(QUIET=True).get_structure('protein', path)
    model = structure[0]
    residues = [r for r in model.get_residues() if is_aa(r)]
    if not str(chain).strip():
        return f"### Protein Length for `{PDB_name}`\n- **Number of Residues:** {len(residues)}"
    wanted = str(chain).strip()
    if wanted not in model:
        raise ValueError(f"Chain '{wanted}' is not present; available chains: {sorted(c.id for c in model)}")
    selected = [r for r in model[wanted] if is_aa(r)]
    return (f"### Protein Length for `{PDB_name}` chain `{wanted}`\n"
            f"- **Number of Residues in chain {wanted}:** {len(selected)}\n"
            f"- **Number of Residues in the whole entry:** {len(residues)}")

def analyze_protein_seq_from_PDB(PDB_name: str) -> str:
    """Read observed first-model protein chains with exact byte provenance.

    Args:
        PDB_name: An explicitly uploaded PDB path, unique uploaded basename
            (with or without .pdb), public task asset, or current-task artifact.
            A bare four-character PDB ID may instead fetch the RCSB snapshot.
            Arbitrary non-uploaded local paths are not accepted.

    Returns:
        JSON-encoded string retaining pdb (the original caller identifier) and
        chain_sequences (chain ID to observed amino-acid sequence). Additional
        source_sha256 is the hash of the same bytes parsed by Bio.PDB, model_id
        is0, and sequence_basis states the first-model observed-residue scope.
        Missing residues are not filled from SEQRES; MSE is mapped to M and
        other recognized noncanonical residues use Bio.SeqUtils.seq1 defaults.
        Empty nonprotein chains may remain empty; an entry without any observed
        amino-acid residues fails. This is not a full-sequence completeness,
        chemical modification, biological assembly or molecular-mass claim.

    Raises:
        ValueError/FileNotFoundError: Invalid identity, unauthorized local path,
            empty/over25MiB/non-ASCII/invalid PDB, or no protein residues.
    """
    import hashlib
    import io
    from Bio.PDB import PDBParser, is_aa
    from Bio.SeqUtils import seq1
    from tools.implementations.general.research_data import _public_source_path

    if not isinstance(PDB_name, str) or not PDB_name.strip():
        raise ValueError("PDB_name must identify an uploaded PDB or a bare PDB ID")
    filename = PDB_name if PDB_name.lower().endswith('.pdb') else PDB_name + '.pdb'
    try:
        path = _public_source_path(filename)
    except (PermissionError, FileNotFoundError):
        # Only an actual bare identifier can invoke the legacy RCSB fetch.
        # An absolute/relative unuploaded path never becomes a remote-ID alias.
        if not re.fullmatch(r"[0-9][A-Za-z0-9]{3}(?:\.pdb)?", PDB_name, flags=re.IGNORECASE):
            raise
        identifier = PDB_name[:-4] if PDB_name.lower().endswith('.pdb') else PDB_name
        with requests.Session() as session:
            session.trust_env = False
            response = request_with_retries(session, "GET", f"https://files.rcsb.org/download/{identifier.upper()}.pdb", timeout=30)
        response.raise_for_status()
        # Keep remote bytes in memory: fetching a new ID must never write into
        # the directory of an uploaded or immutable public task attachment.
        raw = response.content
    else:
        raw = Path(path).read_bytes()
    if not raw or len(raw) > 25 * 1024 * 1024:
        raise ValueError("PDB must be nonempty and at most25MiB")
    structure = PDBParser(QUIET=True).get_structure('protein', io.StringIO(raw.decode('ascii')))
    if not len(structure):
        raise ValueError("PDB contains no parsed model")
    chains = {
        chain.id: ''.join(seq1(r.resname, custom_map={'MSE': 'M'}) for r in chain if is_aa(r))
        for chain in structure[0]
    }
    if not any(chains.values()):
        raise ValueError("PDB contains no observed amino-acid residues")
    return json.dumps({
        'pdb': PDB_name,
        'chain_sequences': chains,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'model_id': 0,
        'sequence_basis': 'First parsed model, observed amino-acid residues only; no SEQRES completion or missing-residue inference; MSE maps to M.',
    })


def calculate_energy_from_sequence(sequence):
    """Retired imprecise mechanical-property contract."""
    raise NotImplementedError('Unqualified physical-unit prediction retired; use PredictNormalizedProteinMechanics for dimensionless model estimates only')

def calculate_force_from_sequence(sequence):
    """Retired imprecise mechanical-property contract."""
    raise NotImplementedError('Unqualified physical-unit prediction retired; use PredictNormalizedProteinMechanics for dimensionless model estimates only')


def calculate_force_energy_from_sequence(sequence):
    """Retired imprecise mechanical-property contract."""
    raise NotImplementedError('Unqualified physical-unit prediction retired; use PredictNormalizedProteinMechanics for dimensionless model estimates only')

def fix_pdb_file(original_pdb_path, fixed_pdb_path):
    """Retired: a fabricated CRYST1 cell is not a scientific structure repair."""
    raise NotImplementedError("FixPDBFile is retired: dummy crystallographic dimensions are not inferred data; retain source metadata or use explicit structure-quality inspection")

    #print(f"Fixed PDB file written to {fixed_pdb_path}")
        
def fold_protein(sequence):
    """
    Predicts the 3D structure of a protein from its sequence and saves it to a PDB file.

    Args:
        sequence (str): Amino acid sequence of the protein.
    """
    name="DefaultProtein"
    filename = 'temp.fasta'
    output_path = code_dir
    fasta_content = f">{name}\n{sequence}\n"

    with open(filename, "w") as f:
        f.write(fasta_content)
        
    executable = os.environ["SCITOOL_OMEGAFOLD_EXECUTABLE"]
    os.makedirs(output_path, exist_ok=True)
    subprocess.run([executable, filename, output_path, "--model", "2", "--device", "cpu"], check=True, timeout=1800)

    original_pdb_path = os.path.join(Config().UPLOAD_FILES_BASE_PATH or code_dir, f"{name}.pdb")
    fixed_pdb_path = original_pdb_path  # In this case, we overwrite the original file
    fix_pdb_file(original_pdb_path, fixed_pdb_path)

    return f"{name}.pdb"

def generate_sequence_from_energy(energy):
    """Retired imprecise mechanical-property contract."""
    raise NotImplementedError('GenerateEnergy task and inverse energy normalization are not established; capability retired')

def get_FASTA_from_name(protein_name: str) -> str:
    """
    Fetches the FASTA sequence of a protein by its name from EBI protein API.

    Args:
        protein_name (str): The name of the protein to fetch the FASTA sequence for.

    Returns:
        str: A Markdown formatted string containing the FASTA sequence of the protein
             or an error message if the protein cannot be found or request fails.
    """
    size = 128
    requestURL = f"https://www.ebi.ac.uk/proteins/api/proteins?offset=0&size={size}&protein={protein_name}"
    markdown_output = f"### FASTA Sequence for Protein: `{protein_name}`\n\n"
    
    try:
        with requests.Session() as session:
            session.trust_env = False
            r = request_with_retries(session, "GET", requestURL, headers={"Accept": "application/json"}, timeout=20)
        r.raise_for_status()  # This will raise an HTTPError if the response was an error
        responseBody = r.text
        json_object = json.loads(responseBody)
        
        if len(json_object) > 0:
            fasta_sequence = json_object[0]['sequence']['sequence']
            markdown_output += f"Matched accession: {json_object[0]['accession']}\n"
            markdown_output += f"```\n{fasta_sequence}\n```"
        else:
            markdown_output += "No results found."
    except Exception as e:
        markdown_output += f"Error occurred: {str(e)}"

    return markdown_output

def send_expasy_request(url, data):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        # "Referer": "https://web.expasy.org/protparam/",
    }

    response = requests.post(url, headers=headers, data=data, timeout=60)
    response.raise_for_status()
    return response

def sequence_to_pdb(sequence: str) -> dict:
    """
    EsmFold: Convert the sequence of the protein into 3D structures and generate PDB format files and calculate the residue accuracy of protein sequences, i.e., the plddt value. which return a PDF file content and residue accuracy.

    Args:
        sequence (str): The sequence of the protein.

    Returns:
        str: The text content with 3D structures.
    """
    data = {
        "seq": sequence,
    }
    response = send_expasy_request(url=os.environ["SCITOOL_ESMFOLD_ENDPOINT"], data=data)
    result = json.loads(response.text)["msg"]
    
    target_directory = "DataFiles/pdb/code_protein"
    os.makedirs(target_directory, exist_ok=True)
    
    filename = os.path.join(target_directory,f"alpha_protein.pdb")
    with open(filename, "w") as f:
        f.write(result["output"][0])
    result["output"][0] = {os.path.abspath(filename)}

    output = f'The file has been stored with the name alpha_protein.pdb.\nThe mutated plddt values were {result["plddt"][0]}'
    
    return output

def calculate_protein_ANM(protein_name: str, n_modes: int = 10, cutoff: float = 12.0) -> str:
    """
    Calculates the Anisotropic Network Model (ANM) for a given protein structure.

    Args:
        protein_name (str): Name of the protein structure file (with or without .pdb extension).
        n_modes (int): Number of normal modes to calculate. Default is 10.
        cutoff (float): Cutoff distance for ANM calculations. Default is 12.0 Å.

    Returns:
        str: A Markdown formatted string that lists the first 'n_modes' eigenvalues
             from the ANM calculation or an error message if the calculation fails.
    """
    import prody
    protein_structure_path = _local_pdb(protein_name)

    markdown_output = f"### ANM Calculation Results for `{protein_name}`\n\n"
    markdown_output += f"- **Number of Modes**: `{n_modes}`\n"
    markdown_output += f"- **Cutoff Distance**: `{cutoff}` Å\n\n"
    markdown_output += "**Eigenvalues**:\n\n"

    try:
        protein = prody.parsePDB(protein_structure_path)
        anm = prody.ANM('protein_anm')
        anm.buildHessian(protein, cutoff=cutoff)
        anm.calcModes(n_modes=n_modes)

        eigenvalues = anm.getEigvals()[:n_modes].round(4)  # Correct method to get eigenvalues
        for i, eigenvalue in enumerate(eigenvalues):
            markdown_output += f"- Mode {i+1}: `{eigenvalue}`\n"
    except Exception as e:
        markdown_output += f"Error occurred during ANM calculation: {str(e)}\n"

    return markdown_output


def analyze_protein_structure(protein_name: str) -> str:
    """
    Analyzes the secondary structure composition of a given protein structure.

    Args:
        protein_structure_path (str): Path to the protein's PDB file.

    Returns:
        str: A Markdown formatted string summarizing the composition of the secondary structures
             in the protein, or an error message if the analysis fails.
    """
    from Bio.PDB import PDBParser, DSSP

    try:
        # Resolve an uploaded structure or fetch a four-character PDB ID from RCSB.
        protein_structure_path = _local_pdb(protein_name)

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure('protein_structure', protein_structure_path)
        model = structure[0]
        executable = os.getenv("SCITOOL_DSSP_EXECUTABLE", str(local_root() / "external_sources/dssp/run_mkdssp"))
        dssp = DSSP(model, protein_structure_path, dssp=executable)

        # Initialize a dictionary for secondary structure counts
        secondary_structure_counts = {
            'H': 0,  # Alpha helix
            'B': 0,  # Isolated beta-bridge
            'E': 0,  # Extended strand
            'G': 0,  # 3-helix (3/10 helix)
            'I': 0,  # 5 helix (pi-helix)
            'T': 0,  # Hydrogen bonded turn
            'S': 0,  # Bend
            'P': 0,  # Poly-proline helices
            '-': 0   # None
        }

        # Count each secondary structure type
        for residue in dssp:
            secondary_structure_counts[residue[2]] += 1
        
        # Calculate the total number of residues with assigned secondary structure
        total_residues = sum(secondary_structure_counts.values())
        
        # Calculate the percentage content for each secondary structure type
        secondary_structure_percentages = {ss: (count / total_residues * 100) for ss, count in secondary_structure_counts.items()}
     
    # Return the results as a JSON string
        return json.dumps(secondary_structure_percentages, indent=4)
    except Exception as e:
       return f"erro with {e}"
def design_protein_alpha(length: int) -> str:
    """
    Designs a protein with an alpha structure based on a given length and generates its structure file in PDB format.

    Args:
        length (int): Length of the protein to be designed.

    Returns:
        str: A Markdown formatted string describing the generated protein and its file location.
    """
    _load_chroma_dependencies()
    # 指定使用第二张 GPU
    device = torch.device(os.getenv("SCITOOL_PROTEIN_DEVICE", "cpu"))
    return design_protein_from_CATH(length, "alpha_protein", "1", steps=300, devices=device)


def design_protein_beta(length: int) -> str:
    """
    Designs a protein with a beta structure based on a given length and generates its structure file in PDB format.

    Args:
        length (int): Length of the protein to be designed.

    Returns:
        str: A Markdown formatted string describing the generated protein and its file location.
    """
    _load_chroma_dependencies()
    device = torch.device(os.getenv("SCITOOL_PROTEIN_DEVICE", "cpu"))
    return design_protein_from_CATH(length, "beta_protein", "2.40", steps=300, devices=device)


def design_protein_alpha_beta(length: int) -> str:
    """
    Designs a protein with an alpha-beta structure based on a given length and generates its structure file in PDB format.

    Args:
        length (int): Length of the protein to be designed.

    Returns:
        str: A Markdown formatted string describing the generated protein and its file location.
    """
    _load_chroma_dependencies()
    device = torch.device(os.getenv("SCITOOL_PROTEIN_DEVICE", "cpu"))
    return design_protein_from_CATH(length, "alpha_beta_protein", "3.30", steps=300, devices=device)
def design_protein_from_CATH(length: int, name: str, CATH_ANNOTATION: str, steps: int = 300, devices: str = 'cpu') -> str:
    """
    Designs a protein based on a given CATH annotation and generates its structure file in PDB format.

    Args:
        length (int): Length of the protein to be designed.
        name (str): Name for the generated protein structure file.
        CATH_ANNOTATION (str): CATH classification used to guide the protein design.
        steps (int): Number of sampling steps for protein generation. Default is 300.
        devices (str): Computing device to use ('cpu' or 'cuda'). Default is 'cpu'.

    Returns:
        str: A Markdown formatted string describing the generated protein and its file location.

    Raises:
        Exception: If there's an issue with generating the protein.
    """
    _load_chroma_dependencies()
    try:
        # Initialize Chroma and load the classifier model
        chroma = Chroma(device=devices)
        
        proclass_model = graph_classifier.load_model("named:public", device=devices)
        conditioner = conditioners.ProClassConditioner("cath", CATH_ANNOTATION, model=proclass_model)

        # Generate protein based on CATH annotation
        cath_conditioned_protein, _ = chroma.sample(
            samples=1,
            steps=steps,
            conditioner=conditioner,
            chain_lengths=[int(length)],
            full_output=True
        )

        # Construct the file name and save the protein structure
        pdb_filename = f'{name}.pdb'
        pdb_path = os.path.join(Config().UPLOAD_FILES_BASE_PATH or code_dir, pdb_filename)
        os.makedirs(os.path.dirname(pdb_path), exist_ok=True)  # Create directory if it doesn't exist

        cath_conditioned_protein.to(pdb_path)
        sequence = cath_conditioned_protein.sequence()

        # Map CATH_ANNOTATION to corresponding type
        cath_annotation_mapping = {"1": "alpha", "2.40": "beta", "3.30": "alpha-beta"}
        cath_annotation_str = cath_annotation_mapping.get(CATH_ANNOTATION, CATH_ANNOTATION)

        # Format and return the result
        result_md = f"""## Protein Design Result
- **Protein Filename**: `{name}`
- **CATH Annotation**: `{cath_annotation_str}`
- **Sequence Length**: `{length}`

**Protein Sequence**:  
`{sequence}`"""

        return result_md
    except Exception as e:
        error_md = f"Error occurred during protein design: {str(e)}"
        return error_md


def design_protein_from_length(length: str):
    """
    Designs a new protein based on a specified length, optionally guided by a caption, 
    and saves the protein structure as a PDB file. Returns a detailed Markdown formatted description.

    Args:
        length (int): The desired length of the protein.

    Returns:
        str: A Markdown formatted string with details about the designed protein or an error message.
    """
    _load_chroma_dependencies()
    try:
        name = 'temp'
        caption=''
        device= 'cpu'
        steps= 300
        length = int(length)
        # Initialize Chroma with specified device
        chroma = Chroma(device='cpu')

        # Determine if a caption is provided to guide the protein design
        if caption:
            print(f"We use this caption to generate a protein: {caption}")
            procap_model = procap.load_model("named:public", device=device, strict_unexpected=False)
            conditioner = conditioners.ProCapConditioner(caption, -1, model=procap_model)
        else:
            conditioner = None

        # Sample a protein based on the specified length and (optional) caption
        protein = chroma.sample(chain_lengths=[length], steps=steps, conditioner=conditioner)

        # Save the designed protein structure to a PDB file
        pdb_filename = f"{name}.pdb"
        pdb_path = os.path.join(Config().UPLOAD_FILES_BASE_PATH or code_dir, pdb_filename)
        print(f"pdb_path:{pdb_path}")
        os.makedirs(os.path.dirname(pdb_path), exist_ok=True)  
        protein.to(pdb_path)

        # Retrieve the protein sequence
        sequence = protein.sequence()

        # Create a Markdown formatted string to summarize the results
        result_md = f"""
## Designed Protein Summary

- **Name**: `{name}`
- **Length**: `{length}`
- **Caption**: `{caption}`
- **Sampling Steps**: `{steps}`
- **PDB File**: `{pdb_filename}`
- **Sequence**:
    ```
    {sequence}
    ```
"""

        return result_md
    except Exception as e:
        error_md = f"Error occurred during protein design: {str(e)}"
        return error_md

def save_to_csv_file(input_json: str) -> str:
    """Export JSON table data through the General CSV primitive."""
    from tools.implementations.general.csv_export import save_to_csv_file as export
    return export(input_json)

def fetch_protein_structure_from_PDBID(PDB_id: str) -> str:
    """
    Fetches the protein structure file (.pdb) for the given PDB ID and saves it to a specified directory.

    Args:
        PDB_id (str): The PDB ID of the protein to fetch.

    Returns:
        str: A Markdown formatted string describing the outcome of the operation, including the file path of the saved PDB file or an error message.

    Raises:
        Exception: If the PDB ID is not valid or if there's an issue downloading or saving the file.
    """
    try:
        # Ensure PDB ID is a string
        if not isinstance(PDB_id, str):
            raise ValueError("PDB_id must be a string.")
        
        # Define the path for saving the PDB file
        if not re.fullmatch(r"[0-9][a-zA-Z0-9]{3}", PDB_id):
            raise ValueError("Expected a four-character PDB identifier")
        os.makedirs(code_dir, exist_ok=True)
        pdb_file_path = f'{code_dir}/{PDB_id}.pdb'
        
        # Attempt to fetch and save the PDB file
        print(f"Fetching protein structure with PDB ID: {PDB_id}")
        with requests.Session() as session:
            session.trust_env = False
            response = request_with_retries(session, "GET", f"https://files.rcsb.org/download/{PDB_id.upper()}.pdb", timeout=20)
        response.raise_for_status()
        with open(pdb_file_path, "w") as file:
            file.write(response.text)
        fetch_result = pdb_file_path
        
        # Check if fetch was successful
        if fetch_result:
            result_md = f"""## PDB File Fetching Result
- **PDB ID**: `{PDB_id}`
- **Saved File Path**: `{pdb_file_path}`"""
            return result_md
        else:
            raise Exception("Failed to fetch the PDB file.")
    except Exception as e:
        error_md = f"Error occurred during PDB file fetching: {str(e)}"
        return error_md


def calculate_force_from_seq(sequence):
    _load_force_dependencies()
    prompt = f"CalculateForce<{sequence}>"
    print(prompt)
    task = extract_task(prompt, end_task_token='>') + ' '
    model, tokenizer = ForceGPTmodel(model_name=Config().FORCEGPT_MODEL_PATH, device=device)

    sample_output = generate_output_from_prompt(model, device, tokenizer, prompt=task, num_return_sequences=1, num_beams=1, temperature=0.01)
    for sample_output in sample_output:
        result=tokenizer.decode(sample_output, skip_special_tokens=True)  
        extract_data=extract_start_and_end(result, start_token='[', end_token=']')
        
    return json.dumps(extract_data, indent=4)


