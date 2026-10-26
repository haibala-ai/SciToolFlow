import ast
import logging
import requests
import json
from PIL import Image
import html2text

from tools.implementations.shared.http_clients import send_novopro_request


def _novopro_result(response, operation):
    """Decode a NovoPro reply and reject it unless the service reported success.

    The service answers with a two-element list whose first element is the status code. A
    rejected request used to be indexed as though it were a payload, which produced
    plausible-looking but entirely fabricated values while the call still reported success.
    Every caller now goes through this check so a rejection surfaces as an error.
    """
    if not response:
        raise RuntimeError(f"NovoPro did not answer the {operation} request")
    try:
        payload = json.loads(response)
    except Exception:
        try:
            payload = ast.literal_eval(response)
        except Exception as exc:
            raise RuntimeError(f"NovoPro {operation} reply was not decodable: {str(response)[:160]}") from exc
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError(f"NovoPro {operation} reply had an unexpected shape: {str(payload)[:160]}")
    if payload[0] != 1:
        raise RuntimeError(f"NovoPro rejected the {operation} request: {str(payload[1])[:160]}")
    return payload

  
def protein_condonoptimizer(protein):
    """
    This tool optimize the the expression of recombinant gene condons of the protein,

    Input:
        protein: protein sequence

    Returns:
        str: The Markdown content with new sequence.
    """
    try:
        cleaned_protein = protein.replace('\n', '').replace(' ', '')

        url = "https://www.novopro.cn/plus/ppc.php"

        payload = f"sr=co&ez=&sq={cleaned_protein}&og=E.coli&st=Protein"
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://www.novopro.cn',
            'Referer': 'https://www.novopro.cn/tools/codon-optimization.html',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }

        response = requests.request("POST", url, headers=headers, data=payload, timeout=30)

        data = response.text

        data_list = _novopro_result(data, 'protein_condonoptimizer')

        # Gets the value in the list
        new_sequence = data_list[1][0]
        CAI = data_list[1][1]
        newCAI = data_list[1][2]
        GC = data_list[1][7]
        newGC = data_list[1][8]
        generated_markdown = f'''
**Optimized Sequence:** {new_sequence}

**CAI (before optimizing):** {CAI}

**CAI (after optimizing):** {newCAI}

**GC (before optimizing):** {GC}

**GC (after optimizing):** {newGC}
'''

        return generated_markdown
    except Exception as e:
        logging.error(f"Error optimize condon: {e}")


        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error optimize condon: {e}") from e
def DNA_condonoptimizer(protein):
    """
    This tool optimize the the expression of recombinant gene condons of the DNA/RNA,

    Input:
        protein: DNA or RNA sequence. The sequence length must be a multiple of 3。

    Returns:
        str: The Markdown content with new sequence.
    """
    try:
        cleaned_protein = protein.replace('\n', '').replace(' ', '')

        url = "https://www.novopro.cn/plus/ppc.php"

        payload = f"sr=co&ez=&sq={cleaned_protein}&og=E.coli&st=DNA"
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://www.novopro.cn',
            'Referer': 'https://www.novopro.cn/tools/codon-optimization.html',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',

        }

        response = requests.request("POST", url, headers=headers, data=payload, timeout=30)

        data = response.text

        data_list = _novopro_result(data, 'DNA_condonoptimizer')

        # Gets the value in the list
        new_sequence = data_list[1][0]
        CAI = data_list[1][1]
        newCAI = data_list[1][2]
        GC = data_list[1][7]
        newGC = data_list[1][8]
        generated_markdown = f'''
**Optimized Sequence:** {new_sequence}

**CAI (before optimizing):** {CAI}

**CAI (after optimizing):** {newCAI}

**GC (before optimizing):** {GC}

**GC (after optimizing):** {newGC}
'''

        return generated_markdown
    except Exception as e:
        logging.error(f"Error optimize condon: {e}")

# Protein hydrophobicity analysis
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error optimize condon: {e}") from e
def compute_hydrophilicity(protein) -> str:
    """
    This tool compute the hydrophilicity of the protein,
    Args:
        protein (str): protein sequence

    Returns:
        str: The Markdown content with hydrophilicity.

    """

    try:
        cleaned_protein = protein.replace('\n', '').replace(' ', '')
        url = "https://www.novopro.cn/plus/ppc.php"
        payload = f"sr=hp&sq={cleaned_protein}"
        headers = {
             'Accept': '*/*',
             'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
             'Connection': 'keep-alive',
             'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
             'Origin': 'https://www.novopro.cn',
             'Referer': 'https://www.novopro.cn/tools/protein-hydrophilicity-plot.html',
             'Sec-Fetch-Dest': 'empty',
             'Sec-Fetch-Mode': 'cors',
             'Sec-Fetch-Site': 'same-origin',
             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',

    }

        response = requests.request("POST", url, headers=headers, data=payload, timeout=30)

        data = response.text

        data = data.replace(",", "\n").replace("\"", "")
        markdown = f'''
**Hydrophilicity Resuly:** 
**For each line, the format is: position:hydrophobicity.**
{data}

'''
        return markdown
    except Exception as e:
        logging.error(f"Error compute hydrophilicity: {e}")


        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error compute hydrophilicity: {e}") from e
def predict_signalpeptide(protein)-> str:
    """
    This tool predict the signal peptide of the protein.
    Args:
        protein: protein sequence and the type of the protein. You can only input the following four types: euk, arch, Gram-, Gram+. euk means eukaryotes, arch means archaea, Gram- means gram-negative bacteria, Gram+ means gram-positive bacteria.
                format: sequence.type
    Returns:
          str: The Markdown content with signal peptide information.
    """

    try:
        sequence, label = protein.split(".")
        data = {
            "sr": "sgp",
            "sq": sequence,
            "org": label,
        }
        response = send_novopro_request(data)
        data_list = _novopro_result(response, "predict_signalpeptide")
        probability = data_list[1][2]
        type = data_list[1][1]
        cleavage1 = data_list[1][3]
        cleavage2 = data_list[1][4]
        cleavage_probability = data_list[1][5]

        markdown = f'''
**Input Sequence:** {protein}
**Input Type:** {label}
    
**Probability of having a signal peptide:** {probability}
**Type of signal peptide:** {type}
**Cleavage site:** {cleavage1} - {cleavage2}
**Probability of the cleavage site:** {cleavage_probability}

'''
        return markdown
    except Exception as e:
        logging.error(f"Error predict signal peptide: {e}")

# Oligonucleotide (primer) calculator
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error predict signal peptide: {e}") from e
def compute_tm(protein) -> str:
    """
    This tool compute the annealing temperature of an oligonucleotide.
    Args:
        protein: protein sequence.

    Returns:
        str: The Markdown content with melting temperature.

    """
    try:

        data={
            "sr": "oc",
            "sq": protein,
            "mod": "::"
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, "compute_tm")
        
        weight = data_list[1][5]
        temperature1 = data_list[1][8]
        temperature2 = data_list[1][9]

        generated_markdown = f'''
**Input Sequence:** {protein}
**Molecular Weight (g/mole):** {weight}
**annealing Temperature(°C):** {temperature1}-{temperature2}
    
'''
        return generated_markdown
    except Exception as e:
        logging.error(f"Error compute annealing temperature: {e}")

# Polypeptide sequence is converted to SMILES
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error compute annealing temperature: {e}") from e
def convert_polypeptide_to_smiles(protein: str) -> dict:
    """Construct an explicit unmodified linear L-peptide molecular graph locally, without a remote descriptor bundle."""
    from tools.implementations.biology.peptide_molecule import peptide_to_smiles
    return peptide_to_smiles(protein)

def compute_isoelectric_point(sequence):
    """
    This tool compute the isoelectric point of the protein or peptide.
    Args:
        sequence: sequence and type. You can only input the following two types: protein, peptide.
                  format: sequence.type

    Returns:
        str: The Markdown content with isoelectric point.

    """
    try:
        cleaned_sequence = sequence.replace('\n', '').replace(' ', '')
        sequence_name, sequence_type = cleaned_sequence.split(".")
        data = {
            "sr": "ipc",
            "pka" : "IPC_"+sequence_type,
            "sq": sequence_name,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, "compute_isoelectric_point")
        dict_data = data_list[1]
        value = dict_data['IPC_'+sequence_type]
        markdown = f'''
**Input Sequence** {sequence_name}
**Sequence's type** {sequence_type}

**Source of pKa**  IPC_{sequence_type}
**Isoelectric point** {value}
        '''
        return markdown
    except Exception as e:
        logging.error(f"Error compute isoelectric point: {e}")

# Binding energy calculates affinity
# @param_decorator
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error compute isoelectric point: {e}") from e
def compute_affinity(dg, temperature, unit):
    """
    This tool computes the dissociation constant from a molar Gibbs free energy.

    Args:
        dg: molar Gibbs free energy
        temperature: temperature in kelvin
        unit: unit of the Gibbs free energy; accepts kcal, kcal/mol, kj or kJ/mol
              (the upstream service only accepts the tokens "kcal" and "kj").

    Returns:
        str: JSON with the affinity, its unit and the submitted parameters.
    """
    import math
    try:
        value = float(dg)
        kelvin = float(temperature)
    except (TypeError, ValueError) as error:
        raise ValueError("dg and temperature must be numeric") from error
    if not math.isfinite(value) or not math.isfinite(kelvin) or kelvin <= 0:
        raise ValueError("Require a finite Gibbs free energy and a positive temperature in kelvin")
    token = str(unit).strip().lower().replace("/mol", "").replace(" ", "")
    if token in ("kcal", "kcalorie", "kcalories"):
        token = "kcal"
    elif token in ("kj", "kjoule", "kjoules", "kj/mol"):
        token = "kj"
    else:
        raise ValueError("unit must be kcal (kcal/mol) or kj (kJ/mol)")
    response = send_novopro_request({"sr": "dg2kd", "dg": value, "t": kelvin, "u": token})
    if not response:
        raise RuntimeError("NovoPro did not answer the affinity request")
    data_list = _novopro_result(response, 'compute_affinity')
    if not isinstance(data_list, list) or len(data_list) < 2 or data_list[0] != 1 or not isinstance(data_list[1], (int, float)):
        raise RuntimeError("NovoPro rejected the affinity request: " + str(data_list)[:200])
    return json.dumps({"provider": "NovoPro dg2kd", "gibbs_free_energy": value,
                       "input_unit": "kcal/mol" if token == "kcal" else "kJ/mol",
                       "temperature_kelvin": kelvin, "affinity": data_list[1],
                       "affinity_definition": "upstream dg2kd output, retained verbatim"})

# Calculate the molecular weight of the peptide
def compute_polypeptide_weight(sequence):
    """
    This tool compute the Average molecular weight of the polypeptide.
    Args:
        sequence: polypeptide sequence.
    Returns:
        str: The Markdown content with Average molecular weight.
    """
    try:
        cleaned_sequence = sequence.replace('\n', '').replace(' ', '')
        data = {
            "nTerm": "",
            "cTerm": "",
            "disulphideBonds": "",
            "aaCode": "0",
            "sequence": cleaned_sequence
        }

        response = send_novopro_request(data)

        data_list = _novopro_result(response, "compute_polypeptide_weight")
        data_dict = data_list[1]
        weight = data_dict['mw']
        generated_markdown = f'''
**Input Sequence:** {sequence}
    
**Average molecular weight:** {weight}
'''
        return generated_markdown
    except Exception as e:
        logging.error(f"Error compute Average molecular weight: {e}")

# Calculate the polypeptide formula
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error compute Average molecular weight: {e}") from e
def compute_polypeptide_formula(sequence):
    """
    This tool compute the chemical formula of the polypeptide.
    Args:
        sequence: polypeptide sequence.
    Returns:
        str: The Markdown content with chemical formula.
    """
    try:
        cleaned_sequence = sequence.replace('\n', '').replace(' ', '')
        data = {
            "nTerm": "",
            "cTerm": "",
            "disulphideBonds": "",
            "aaCode": "0",
            "sequence": cleaned_sequence
        }

        response = send_novopro_request(data)

        data_list = _novopro_result(response, "compute_polypeptide_formula")
        data_dict = data_list[1]
        formula = data_dict['cf']
        generated_markdown = f'''
**Input Sequence:** {sequence}

**Chemical formula:** {formula}
'''
        return generated_markdown
    except Exception as e:
        logging.error(f"Error compute chemical formula: {e}")

# Calculate the degenerate codon of an amino acid
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error compute chemical formula: {e}") from e
def compute_degeneracy(sequence):
    """
    This tool calculates the optimal degenerate codons that encode one or more input amino acids. It can be applied to library construction.
    Args:
        sequence: amino acid sequence.
    Returns:
        str: The Markdown content with degeneracy.
    """
    try:
        cleaned_sequence = sequence.replace('\n', '').replace(' ', '')
        data = {
            "sr": "degcon",
            "sq": cleaned_sequence
        }

        response = send_novopro_request(data)

        data = response.replace('{', '').replace('},', '\n').replace('[1, [', ' ').replace(']', '').replace('}', '')
        markdown = f'''
**Degeneracy of the amino acid sequence:**
{data}

'''
        return markdown
    except Exception as e:
        logging.error(f"Error compute molecule formula: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error compute molecule formula: {e}") from e


def design_overlappeptidelibrary(pretein):
    """
    This tool design overlapping peptide library.
    Args:
        preotein: pretein sequence. Peptide length(integer). peptide overlap length(integer).The peptide overlap length should be smaller than the peptide length.
                 format: sequence.lenght.overlaplength
    Returns:
        str: The Markdown content with peptide library.
    """
    try:
        sequence, length, overlaplength = pretein.split(".")
        cleaned_sequence = sequence.replace('\n', '').replace(' ', '')
        data = {
            "sr": "plibdsg",
            "seq": cleaned_sequence,
            "lt": "overlap",
            "p": length+"::"+overlaplength
        }

        response = send_novopro_request(data)
        data = _novopro_result(response, 'design_overlappeptidelibrary')
        content = data[1]
        markdown = f'''
**Overlapping Peptide Library. Each line is one result.**

'''
        for item in content:
            markdown += f"- sequence: {item[0]}, Length: {item[1]}, Hydrophobicity value: {item[2]}\n"

        return markdown
    except Exception as e:
        logging.error(f"Error design overlap peptide library: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error design overlap peptide library: {e}") from e


def design_alaninescanninglibrary(protein):
    """
    This tool design peptide library.
    Args:
        preotein: protein sequence.
    Returns:
        str: The Markdown content with peptide library.
    """
    try:
        cleaned_sequence = protein.replace('\n', '').replace(' ', '')
        data = {
            "sr": "plibdsg",
            "seq": cleaned_sequence,
            "lt": "ala",
            "p": ""
        }

        response = send_novopro_request(data)
        data = _novopro_result(response, 'design_alaninescanninglibrary')
        content = data[1]
        markdown = f'''
**Alanine Scanning Library. Each line is one result.**

'''
        for item in content:
            markdown += f"- sequence: {item[0]}, Length: {item[1]}, Hydrophobicity value: {item[2]}\n"

        return markdown
    except Exception as e:
        logging.error(f"Error design alanine scanning library: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error design alanine scanning library: {e}") from e


#Truncation Library
def design_truncationlibrary(protein):
    """
       This tool design truncation peptide library.
       Args:
           preotein: protein sequence.
       Returns:
           str: The Markdown content with peptide library.
       """
    try:
        cleaned_sequence = protein.replace('\n', '').replace(' ', '')
        data = {
            "sr": "plibdsg",
            "seq": cleaned_sequence,
            "lt": "truncation",
            "p": ""
        }

        response = send_novopro_request(data)
        data = _novopro_result(response, 'design_truncationlibrary')
        content = data[1]
        markdown = f'''
    **Truncation Library. Each line is one result.**

    '''
        for item in content:
            markdown += f"- sequence: {item[0]}, Length: {item[1]}, Hydrophobicity value: {item[2]}\n"

        return markdown
    except Exception as e:
        logging.error(f"Error design Truncation library: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error design Truncation library: {e}") from e

#Positional Scanning Library
def design_positionalscanninglibrary(protein_residueposition):
    """
    This tool design positional scanning peptide library.
    Args:
        protein_residueposition: protein sequence. resodue position.(The numbers of residue positions are separated by commas. example:"3,4")
                                    format: sequence.residueposition   example: AIAKFERLQTVTNYFITSLA.2,5
    Returns:
        str: The Markdown content with peptide library.
    """
    try:
        cleaned_sequence = protein_residueposition.replace('\n', '').replace(' ', '')
        sequence, position = cleaned_sequence.split(".")
        position = position.replace("，", ",")
        data = {
            "sr": "plibdsg",
            "seq": sequence,
            "lt": "positional",
            "p": position
        }

        response = send_novopro_request(data)
        data = _novopro_result(response, "positional scanning library")
        content = data[1]
        markdown = f'''
    **Positional Scanning Library. Each line is one result.**

    '''
        for item in content:
            markdown += f"- sequence: {item[0]}, Length: {item[1]}, Hydrophobicity value: {item[2]}\n"

        return markdown
    except Exception as e:
        logging.error(f"Error design positional scanning library: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error design positional scanning library: {e}") from e


def protease_digestion(protein_protease):
    """
    This tool can simulate the hydrolytic behavior of protein-degrading enzymes. Its main purpose is to predict the hydrolysis outcomes of peptide substrates."
    Args:
        protein: protein sequence and protease name.
                 format: sequence.protease
                 Only the following proteases are supported. protease list:
                 alcalase, arg-c_proteinase, asp-n_endopeptidase, asp-n_endopeptidase_glu, bnps_skatole, bnps_skatole
                 caspase_1, caspase_2, caspase_3, caspase_4, caspase_5, caspase_6, caspase_7, caspase_8, caspase_9, caspase_10
                 chymotrypsin, chymotrypsin_low, clostripain, cnbr, enterokinase, factor_xa, formic_acid, glutamyl_endopeptidase
                 granzymeb, hydroxylamine, hcl, iodosobenzoic_acid, lysc, lysn, ntcb, pepsin_ph1.3, pepsin, proline_endopeptidase
                 proteinase_k, staphylococcal_peptidase_i, thermolysin, thrombin, tev, tryspin

    Returns:
          str: The Markdown content with cleavage sites and products.
    """

    try:
        cleaned_sequence = protein_protease.replace('\n', '').replace(' ', '')
        sequence, protease = cleaned_sequence.split('.', 1)
        data = {
            "sr": "protease",
            "seq": sequence,
            "enz": protease
        }
        response = send_novopro_request(data)
        data = _novopro_result(response, "protease_digestion")

        markdown = f'''
***Protease Digestion Results***
input sequence: {sequence}
'''
        if not data[1][0][0]:
            markdown += f'''**{protease}** : This protein cannot be cleaved by {protease}.'''
        else:
            markdown += f'''**{protease}** cleavage site:{data[1][0][0]}  products:{data[1][0][1]}'''

        return markdown
    except Exception as e:
        logging.error(f"Error protease digestion: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error protease digestion: {e}") from e


def CDR_LabelingAntibody(sq, nskm, dskm):
    '''
    This tool label the variable regions of antibodies with CDR and FR regions; Users need to choose a numbering system, and the numbering schemes include: imgt, chothia, kabat, martin; The definition scheme includes chothia, kabat, imgt, and contact. Note: The Kabat numbering scheme is not compatible with the Contact definition scheme. To number the amino acid sequence of antibodies, please visit the antibody sequence numbering tool
    You should provide 3 input arguments.
    Args:
        sequence: antibody sequence
        numbering: numbering schemes
        definition: definition scheme

    Returns:
            str: The Markdown content with CDR and FR regions.

    Note:
        You should input as:'sq=RLSCAASGFTFS, nskm=imgt, dskm=chothia'
    '''
    try:

        numbering = str(nskm).strip().lower()
        definition = str(dskm).strip().lower()
        # The docstring states that the Kabat numbering scheme cannot be combined with the Contact
        # definition scheme. Reject that pair here so the caller receives the reason rather than an
        # opaque error from deeper in the parsing of the service reply.
        if numbering == "kabat" and definition == "contact":
            raise ValueError(
                "The Kabat numbering scheme is not compatible with the Contact definition scheme; "
                "choose chothia, kabat, imgt or contact as the definition with a compatible numbering scheme")

        data ={
            "sr": "cdr",
            "nskm": numbering,
            "dskm": definition,
            "sq": sq,
        }

        response = send_novopro_request(data)
        parsed_data = _novopro_result(response, 'CDR_LabelingAntibody')



        markdown = f'''
***CDR and FR regions***
input sequence: {sq}

**Results**
'''

        # Extract the antibody name and sequence
        for item in parsed_data[1][0]:
            for key, value in item.items():
                markdown += f"Name: {key}\t sequence: {value[1]}\n"
        return markdown
    except Exception as e:
        logging.error(f"Error CDR and FR regions: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error CDR and FR regions: {e}") from e


def number_antibodysequence(sq) -> str:
    '''
        This tool number the amino acid sequence of the antibody; Identify the input sequence and distinguish between immunoglobulin (IG) and T cell receptor (TR); The numbering system includes: IMGT, Chothia, Kabat, Martin (extended version Chothia), and AHo; TR sequences can only be numbered using IMGT or AHo. To label the CDR and FR of antibody variable regions, please use the antibody variable region CDR labeling tool


    Args:
        sq: antibody sequence
        numbering: numbering scheme

    Returns:
        The Markdown content with antibody sequence numbering.

    Notes:
        You should input as:'RLSCAASGFTFS.imgt'
    '''
    try:
        sq, numbering = sq.split('.')
        numbering = numbering.lower()
        data ={
            "sr": "abnum",
            "skm": numbering,
            "ct": "",
            "org":"",
            "sq": sq,
        }
        markdown = f'''
**Antibody sequence number**
Input sequence: {sq}

**IG/TR Structural Domains Results**        
'''

        response = send_novopro_request(data)
        data = _novopro_result(response, 'number_antibodysequence')

        for i in range(len(data[1])):

            first_structure = data[1][i][0]
            second_structure = data[1][i][1]
            species_1, chain_type_1, e_value_1, score_1, seqstart_index_1, seqend_index_1 = first_structure[1]
            species_2, v_gene, v_identity, j_gene, j_identity = second_structure[1]
            markdown += f"{i + 1}. Species: {species_1}\tChain Type: {chain_type_1}\tE-value: {e_value_1}\tBit Score: {score_1}\tSeqstart Index: {seqstart_index_1}\tSeqend Index: {seqend_index_1}\tV Gene: {v_gene}\tV Identity: {v_identity}\tJ Gene: {j_gene}\tJ Identity: {j_identity}\n"

        return markdown
    except Exception as e:
        logging.error(f"Error antibody sequence numbering: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error antibody sequence numbering: {e}") from e

#Loop DNA comparison tool
def align_circularDNA(sequence: str) -> str:
    '''
    This tool aligns circular DNA sequences. Comparing homologous sequences of different species is an important method for reconstructing the evolutionary history of genes in species and their genomes. The circular DNA sequence alignment tool can be applied to sequence alignment of circular nucleic acid molecules, including plasmids, mitochondrial DNA (mtDNA), circular bacterial chromosomes, cccDNA (covalently closed circular DNA), chloroplast DNA (cpDNA), and other plastids.

    Args:
        sequence: DNA sequence. You should input at least two sequences and use '.' to separate them.
        example: ATGCGTATCG.ACGTACGTACG
    Returns:
        str: The Markdown content with alignment results.
       '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '')
        sequence_list = cleaned_sequence.split(".")
        fasta = ""
        for i in range(len(sequence_list)):
            fasta += f">sequence{i+1}\n{sequence_list[i]}\n"

        data = {
            "sr": "csa",
            "seqtype": "dna",
            "outfmt": "clw",
            "sq": fasta,
        }
        markdown = f'''
***Alignment Results***
input sequence: {fasta}

**Results in ClustalW format**
'''
        response = send_novopro_request(data)
        data = _novopro_result(response, 'align_circularDNA')
        markdown += f"{data[1][0]}\n"
        markdown += f"Sum of pairs score: {data[2]}\n"
        for i in range(len(data[1])-4):
            markdown += f"{data[1][i+3]}\n"
        return markdown
    except Exception as e:
        logging.error(f"Error align circular DNA: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error align circular DNA: {e}") from e

#Multiple sequence alignment
def compare_multiple_sequence(sequence: str) ->str:
    '''
    Multiple Sequence Comparison by Log Expectation is a tool used to compare protein or nucleic acid sequences. The average accuracy and speed are better than ClustalW2 or T-Coffee.
    Args:
        sequence: multiple sequence.You should input at least two sequences and use '.' to separate them. example: ATGCGTATCG.ACGTACGTACG
    Returns:
        str: The Markdown content with comparison results of multiple sequences.
    '''
    try:
        sequence_list = _split_sequences(sequence)
        fasta = ""
        for i in range(len(sequence_list)):
            fasta += f">sequence{i+1}\n{sequence_list[i]}\n"

        data = {
            "sr": "msa",
            "seqtype": "",
            "outfmt": "clw",
            "sq": fasta,
        }
        markdown = f'''
***Comparison of multiple sequence***
input sequence: {fasta}

**Results in ClustalW format**
'''
        response = send_novopro_request(data)
        data = _novopro_result(response, 'compare_multiple_sequence')
        markdown += f"{data[1][0]}\n"
        for i in range(len(data[1])-4):
            markdown += f"{data[1][i+3]}\n"

        return markdown
    except Exception as e:
        logging.error(f"Error compare multiple sequences: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error compare multiple sequences: {e}") from e


def _split_sequences(text, minimum=2, maximum=100):
    """Split a sequence group on any non-letter separator ('.', '|', ',', whitespace)."""
    import re as _re
    parts = [part.upper() for part in _re.split(r"[^A-Za-z]+", text.strip()) if part]
    if not minimum <= len(parts) <= maximum:
        raise ValueError(f"Require {minimum}-{maximum} sequences separated by '.', '|', ',' or whitespace")
    return parts


def align_double_sequence(sequence_pair: str) -> str:
    '''
    This tool compares two sequences in global alignment style.
    
    Args:
        sequence_pair: Two sequences separated by a comma '.'.
        
    Returns:
        str: The Markdown content with alignment results of two sequences, including the sequences themselves.
    '''
    try:
        sequence1, sequence2 = _split_sequences(sequence_pair, minimum=2, maximum=2)
        if max(len(sequence1), len(sequence2)) > 10000:
            raise ValueError("Global alignment is limited to 10000 residues per sequence")
        # The upstream NovoPro needle action answers with a rendered SVG image,
        # which is not a usable agent result and overflows the local prompt
        # budget. Use the equivalent Needleman-Wunsch global alignment locally
        # and return compact, auditable text instead.
        from Bio.Align import PairwiseAligner
        scoring = {"match_score": 2.0, "mismatch_score": -1.0,
                   "open_gap_score": -2.0, "extend_gap_score": -0.5}
        aligner = PairwiseAligner(mode="global", **scoring)
        alignment = next(iter(aligner.align(sequence1, sequence2)), None)
        columns = [column for column in zip(str(alignment[0]), str(alignment[1])) if column != ("-", "-")] if alignment is not None else []
        identical = sum(left == right for left, right in columns)
        return json.dumps({
            "implementation": "Bio.Align.PairwiseAligner", "mode": "global",
            "algorithm": aligner.algorithm if alignment is not None else None, "scoring": scoring,
            "sequence1": sequence1, "sequence2": sequence2,
            "score": alignment.score if alignment is not None else 0.0,
            "coordinates_are": "0-based half-open",
            "coordinates": alignment.coordinates.tolist() if alignment is not None else [],
            "compared_columns": len(columns), "identical_columns": identical,
            "identity_percent": 100 * identical / len(columns) if columns else 0.0,
            "alignment": str(alignment) if alignment is not None else "",
            "note": "Replaces the retired NovoPro needle SVG rendering with a local Needleman-Wunsch global alignment",
        }, ensure_ascii=False)
    except Exception as e:
        return f"Error align double sequence: {e}"

#Protein solubility prediction
def predict_protein_solubility(sequence: str) -> str:
    '''
    This tool predict the solubility of the protein based on sequence.
    Args:
        sequence: protein sequence.
    Returns:
        str: The Markdown content with solubility.
    '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '')
        data = {
            "sr": "sol",
            "sq": cleaned_sequence,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'predict_protein_solubility')
        markdown = f'''
***Solubility Prediction***
input sequence: {cleaned_sequence}

Predicted solubility: {data_list[1]}
'''
        return markdown
    except Exception as e:
        logging.error(f"Error predict protein solubility: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error predict protein solubility: {e}") from e

#Prediction of inherently disordered regions of proteins
def predict_inherent_disordered_regions(sequence: str):
    '''
    This tool predict the inherent disordered regions of the protein based on sequence.
    Args:
        sequence: protein sequence.
    Returns:
        picture: The picture of the inherent disordered regions. JPG format.
    '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '')
        data = {
            "sr": "idr",
            "sq": cleaned_sequence,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'predict_inherent_disordered_regions')
        temp_list = data_list[1].split('/')
        path ="https://www.novopro.cn/plus/tmp/" + temp_list[1]
        image = Image.open(requests.get(path, stream=True, timeout=30).raw)
        return image
    except Exception as e:
        logging.error(f"Error predict inherent disordered regions: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error predict inherent disordered regions: {e}") from e
        
#Double sequence contrast (local contrast)
def align_double_sequence_local(sequence: str) -> str:
    '''
    This tool compare two sequences in local alignment style.Local alignment: Unlike global alignment, local alignment does not require alignment between two complete sequences, but instead uses certain local region fragments in each sequence for alignment. The demand for it lies in the discovery that although some protein sequences exhibit significant differences in overall sequence, they can independently perform the same function in certain local regions, and the sequences are quite conservative. At this point, it is obvious that relying on global alignment cannot obtain these locally similar sequences. Secondly, in eukaryotic genes, intron fragments exhibit great variability, while exon regions are relatively conserved. At this point, global alignment shows its limitations and cannot identify these local similarity sequences. Its representative is the Smith Waterman local alignment algorithm.
    Args:
        sequence: two sequence.You should input two sequences and use '.' to separate them. example: ATGCGTATCG.ACGTACGTACG
    Returns:
        str: The Markdown content with alignment results of two sequences.
    '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '')
        seq1, seq2 = cleaned_sequence.split('.')
        fasta = f"[\">sequence1\\n{seq1}\",\">sequence2\\n{seq2}\"]"
        data = {
            "sr": "needle",
            "sq": fasta,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'align_double_sequence_local')
        markdown = f'''
***Local alignment of two sequences***
input sequence: \n{fasta}   

**Alignment Results**
    {data_list[1]}
    '''
        return markdown
    except Exception as e:
        logging.error(f"Error local align double sequence: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error local align double sequence: {e}") from e

#Protein motif analysis
def analyse_protein_moti(sequence: str) -> str:
    '''
    This tool analyse the motif of the protein based on sequence. "Motif (motif) refers to a conserved region in a DNA or protein sequence, or a small sequence pattern shared by a group of sequences. In biology, it is a data-driven mathematical statistical model. Functional prediction can be made based on protein sequence characteristics (such as protein motifs). Proteins with the same motif or domain can be classified into a large group called super families. Protein domains: are structural entities that typically represent a part of a protein's independent folding and movement functions. Therefore, proteins are often constructed from different combinations of these structural domains. At the motif level, the main emphasis is on the concept of structure rather than function, while domain emphasizes functional units, so it is mostly referred to as domain by function. If a protein has a Ca+2 binding domain, it means that the main function of a certain domain of the protein is to bind Ca+2, and the domain must have a Ca+2 binding motif (E-F hand motif) that provides Ca+2 binding.
    Args:
        sequence: protein sequence.
    Returns:
        str: The Markdown content with motif.
    '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '')
        data = {
            "sr": "motifscan",
            "sq": cleaned_sequence,
        }
        markdown = f'''
***Motif Analysis***
input sequence: {cleaned_sequence}
    
**Results**
'''
        response = send_novopro_request(data)

        data_list = _novopro_result(response, 'analyse_protein_moti')

        for key, value in data_list[1].items():
            markdown += f"Motif type: {key};\n"
            for i in range(len(value)):
                markdown += f"position  :{value[i][0]}--{value[i][1]}   sequence:{cleaned_sequence[value[i][0]-1:value[i][1]]}\n"
            markdown += f"-----------------------------------------------------\n"
        return markdown
    except Exception as e:
        logging.error(f"Error analyse protein motif: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error analyse protein motif: {e}") from e

#Sequence similarity calculation
def calculate_sequence_similarity(sequence_group: str) -> str:
    '''
    Sequence similarity calculation takes a set of aligned sequences (FASTA or GCG format) as input to calculate their similarity
    Args:
        sequence_group: includes a set of sequences and a group of amino acid.
                        You should use '.' to separate different sequences.
                        You should use ',' to separate different amino acid.
                        You should use ':' to separate sequences and amino acids.
                        Example: ATGCGTATCG.ACGTACGTACG.ACGTACGTACG:GAVLI,FYW,CM
    Returns:
        str: The Markdown content with sequence similarity.
    '''
    try:
        cleaned_sequence = sequence_group.replace(' ', '').replace('\n', '')
        sequence, amino_acid = cleaned_sequence.split(':')
        sequence_list = sequence.split('.')
        fasta = ""
        i = 0
        for item in sequence_list:
            fasta += f">sequence{i + 1}\n{item}\n"
            i += 1

        data = {
            "sr": "identsim",
            "sq": fasta,
            "aagroup": amino_acid,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'calculate_sequence_similarity')


        markdown = f'''
**Sequence Similarity Calculation**

input sequence:    
'''
        i = 0
        for item in sequence_list:
            markdown += f">sequence{i + 1}\n{item}\n"
            i += 1
        markdown += f"\n"
        markdown += data_list[1].replace('<br />', '').replace('<b>', '').replace('</b>', '').replace('\n  ', '\n')
        return markdown
    except Exception as e:
        logging.error(f"Error calculate sequence similarity: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error calculate sequence similarity: {e}") from e


#Open reading frame ORF lookup
def find_orf(sequence_prolen: str) -> str:
    '''
   The ORF search tool can help you find open reading frames in DNA sequences, and the returned results include the start and end positions of the ORF as well as the translation results of the open reading frames.
    Args:
        sequence_prolen: DNA sequence and prolen. Only return codons with a reading frame length greater than pronlen. Please use '.' to separate sequence and prolen. Example: ATGCGTATCG.30
    Returns:
        str: The Markdown content with ORF.
    '''
    try:
        cleaned_sequence = sequence_prolen.replace(' ', '').replace('\n', '')
        sequence, prolen = cleaned_sequence.split('.')
        sequence = f">sequence\n" + sequence

        data = {
            "sr": "orfind",
            "sq": sequence,
            "startcondon": "any",
            "strand": "direct",
            "prolen": prolen,
            "startpos": "0",
            "condontab": "transl_table=1",
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'find_orf')
        result = data_list[1].replace('<div class="info">', '').replace('</div>&gt;', '\n>').replace('<br />', '\n').replace('<br>', '').replace('<br/>', '').replace('&gt;', '>').replace("\n\n",'\n')
        markdown = f'''
***ORF Results***
input sequence: {cleaned_sequence}

**Results**
{result}
'''
        return markdown

    except Exception as e:
        logging.error(f"Error find ORF: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error find ORF: {e}") from e


#DNA sequences are translated into amino acid sequences
def DNA_to_AminoAcid(sequence: str)-> str:
    '''
    This tool translate DNA sequence to protein(amino acid) sequence.

    Args:
        sequence: DNA sequence.
    Returns:
        str: The Markdown content with amino acid sequence.
    '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '')
        data = {
            "sr": "translate",
            "sq": cleaned_sequence,
            "pos": "0",
            "strand": "direct",
            "genecode": "transl_table=1"
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'DNA_to_AminoAcid')
        result = data_list[1].replace('&gt;rf 1 Untitled<br />\n', '')
        result = result.replace('<br/>', '').replace('<br />', '')
        markdown = f'''
***Translation Results***
input DNA sequence: {cleaned_sequence}

**Results**
Protein sequence: {result}
'''
        return markdown
    except Exception as e:
        logging.error(f"Error translate DNA to amino acid: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error translate DNA to amino acid: {e}") from e


#Look for repeats in DNA sequences
def search_repeat_DNAsequence(sequence_length: str) -> str:
    '''
    This tool search repeat DNA sequence in DNA sequence.
    Args:
        sequence_length: DNA sequence.Minimum repeat sequence length. You should use '.' to separate sequence and length. Example: ATGCGTATCG.3
    Returns:
        str: The Markdown content with repeat DNA sequence. The markdown includs sequence, length and position(s). Position(s) start from 1.
    '''
    try:

        cleaned_sequence = sequence_length.replace(' ', '').replace('\n', '')
        sequence, length = cleaned_sequence.split('.')
        data = {
            "sr": "rs",
            "st": "DNA",
            "sq": sequence,
            "ml": length,
            "ln": len(sequence),
        }
        markdown = f'''
***Repeat DNA Sequence Search***
input sequence: {sequence}
Minimum repeat sequence length: {length}

**Results**
'''
        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'search_repeat_DNAsequence')
        result = data_list[1]
        for item, value in result:
            markdown += f"sequence: {item}\t length: {len(item)}\t position(s): {[x + 1 for x in value]}\n"
        return markdown
    except Exception as e:
        logging.error(f"Error search repeat DNA sequence: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error search repeat DNA sequence: {e}") from e


#Look for repeats in protein sequences
def search_repeat_proteinsequence(sequence_length: str) -> str:
    '''
    This tool search repeat protein sequence in DNA sequence.
    Args:
        sequence_length: Protein sequence. Minimum repeat sequence length. You should use '.' to separate sequence and length. Example: ATGCGTATCG.3
    Returns:
        str: The Markdown content with repeat protein sequence. The markdown includs sequence, length and position(s). Position(s) start from 1.
    '''
    try:

        cleaned_sequence = sequence_length.replace(' ', '').replace('\n', '')
        sequence, length = cleaned_sequence.split('.')
        data = {
            "sr": "rs",
            "st": "Protein",
            "sq": sequence,
            "ml": length,
            "ln": len(sequence),
        }
        markdown = f'''
***Repeat Protein Sequence Search***
input sequence: {sequence}
Minimum repeat sequence length: {length}

**Results**
'''
        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'search_repeat_proteinsequence')
        result = data_list[1]
        for item, value in result:
            markdown += f"sequence: {item}\t length: {len(item)}\t position(s): {[x + 1 for x in value]}\n"
        return markdown
    except Exception as e:
        logging.error(f"Error search repeat protein sequence: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error search repeat protein sequence: {e}") from e


# Find a palindromic sequence
def search_palindromic_sequences(sequence_lengthrange: str) -> str:
    '''
    This tool searches for palindrome sequences in the sequence and enters the length range of nucleic acid sequences and palindrome sequences in the text box below. The 'U' in the nucleic acid sequence will be replaced with 'T'
    Args:
        sequence_lengthrange: DNA sequence. The length range of palindrome sequences. It includs two integers，like 2-6;  You should use '.' to separate sequence and length. Example: ATGCGTATCG.2-6
    Returns:
        str: The Markdown content with palindromic sequences. The markdown includs sequence, length and position(s). Position(s) start from 1.
    '''
    try:

        cleaned_sequence = sequence_lengthrange.replace(' ', '').replace('\n', '')
        sequence, lengthrange = cleaned_sequence.split('.')
        lengthrange = lengthrange.replace('-', '::')
        data = {
            "sr": "psf",
            "sq": sequence,
            "len": lengthrange,
        }
        markdown = f'''
***Palindromic Sequences Finder***
input sequence: {sequence}

**Results**
'''
        response = send_novopro_request(data)
        data_list = _novopro_result(response, "search_palindromic_sequences")
        result = data_list[1]
        for key in result:
            value = result[key]
            markdown += f"Position: {int(key)+1}\t Palindromi Sequence: {value}\t Length: {len(value)}\n"
        return markdown

    except Exception as e:
        logging.error(f"Error search palindromic sequences: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error search palindromic sequences: {e}") from e


#Calculate degenerate codons encoding amino acids
def degcon2aa(codon: str) -> str:
    '''
    This tool calculate amino acid by degenerate codon. Input a degenerate codon (3nt) and calculate the amino acid encoded by that codon
    Args:
        codon: degenerate codon. Only degenerate bases and 'A','T','C','G' are allowed. Length must be 3.
    Returns:
        str: The Markdown content with amino acid.
    '''
    try:
        cleaned_condon = codon.replace(' ', '').replace('\n', '')
        data = {
            "sr": "degcon2aa",
            "sq": cleaned_condon,
        }
        markdown = f'''
***Calculate Amino Acid by Degenerate Codon***
input degenerate codon: {cleaned_condon}

**Results**
'''
        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'degcon2aa')
        result = data_list[1]

        for key in result:
            value = result[key]
            markdown += f"Encode amino acid: {key}\t Codon: {value}\t Number of codons: {len(value)}\n "

        return markdown
    except Exception as e:
        logging.error(f"Error calculate amino acid by degenerate codon: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error calculate amino acid by degenerate codon: {e}") from e


#Protein localization signal prediction
def predict_nls(sequence_threshold: str) -> str:
    '''
    This tool predict nuclear localization sequence of protein based on sequence. Nuclear localization sequence or signal - a structural domain of a protein, usually a short amino acid sequence that can interact with the nuclear carrier to transport the protein into the nucleus. NLS has no special requirements for the proteins it connects to and is not cleaved after nuclear input.
    Args:
        sequence_threshold: protein sequence and posterior probability threshold. You should use ':' to separate sequence and threshold. Example: ATGCGTATCG:0.5
    Returns:
        str: The Markdown content with protein nuclear localization sequence.
    '''
    try:
        cleaned_sequence = sequence_threshold.replace(' ', '').replace('\n', '')
        sequence, threshold = cleaned_sequence.split(':')
        data = {
            "sr": "nls",
            "sq": sequence,
            "mod": "1",
            "threshold": threshold,
        }
        markdown = f'''
***Protein Nuclear Localization Sequence Prediction***
input sequence: {sequence}

**Results**
'''
        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'predict_nls')
        result = data_list[1]
        if result == 1:
            return "The protein does not have a nuclear localization sequence under the current posterior probability threshold."
        for item in result[0]:
            item_list = item.split('\t')
            markdown += f"Probability: {item_list[0]}\tStart Position: {item_list[1]}\t\tEnd Position: {item_list[2]}\t Sequence: {item_list[3]} \n"
        return markdown
    except Exception as e:
        logging.error(f"Error predict protein nuclear localization sequence: {e}")
        # Surface the failure instead of returning None, so the caller receives an
        # actionable reason (including upstream or input-format problems) rather than
        # an opaque empty result.
        raise RuntimeError(f"Error predict protein nuclear localization sequence: {e}") from e


# Small molecule similarity calculation
def compute_smiles_similarity(smiles: str) -> str:
    '''
    This tool calculate the similarity of small molecules based on SMILES.
    Args:
        smiles: SMILES. You should use '.' to separate different SMILES. Example: C1CCCCC1.C1CCCCC1
    Returns:
        str: The Markdown content with similarity.
    '''
    try:
        cleaned_smiles = smiles.replace(' ', '').replace('\n', '')
        smiles = cleaned_smiles.replace('.', '\n')
        data = {
            "sr": "sim",
            "sq": smiles,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'compute_smiles_similarity')
        result = data_list[1]
        if result == '':
            return "No similarity."
        markdown = f'''
***Small Molecule Similarity Calculation***
input SMILES: 
'''
        smiles_list = smiles.split('\n')
        for i in range(len(smiles_list)):
             markdown += f"No.{i + 1} {smiles_list[i]}\n"
        markdown += f"\n***Similarity Resultes***\n"
        result = ast.literal_eval(result)
        for i in range(len(result)):
            markdown += str(result[i]).replace('[\'', '').replace('\',', '\t\tSimilarity(%)').replace(']', '\n')

        return markdown
    except Exception as e:
        logging.error(f"Error calculate small molecule similarity: {e}")


# Calculating DNA molecular weight
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error calculate small molecule similarity: {e}") from e
def calculate_DNA_weight(sequence_para: str) -> str:
    '''
    This tool calculate the molecular weight of DNA based on sequence.
    Args:
        sequence: DNA sequence.
        strand: Single-stranded or double-stranded DNA. You should input 'single' or 'double'.
        topology: Linear or circular DNA. You should input 'linear' or 'circular'.
        you should use ',' to separate different sequences. you should use ',' to separate different parameters. you should use '.' to separate sequence and parameters.
        example:'name1:garkbdctymvhu, name2:garkbdctymvhu. strand=single, topology=linear'
    Returns:
        str: The Markdown content with molecular weight.
    '''
    try:
        cleaned_sequence = sequence_para.replace(' ', '').replace('\n', '')
        sequence, parameters = cleaned_sequence.split('.')
        strand, topology = parameters.split(',')
        strand = strand.replace('strand=', '')
        topology = topology.replace('topology=', '')
        sequence_list = sequence.split(',')
        fasta = ''
        for item in sequence_list:
            name, sq = item.split(':')
            fasta += f">{name}\n{sq}\n"
        data = {
            "sr": "dnamw",
            "sq": fasta,
            "strand": strand,
            "top": topology,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'calculate_DNA_weight')
        result = data_list[1]
        result = result.replace('<div class="info">', '\n').replace('</div>', '\n')
        markdown = f'''
***DNA Molecular Weight Calculator***
input sequence: 
{fasta}
**Results**{result}
'''
        return markdown
    except Exception as e:
        logging.error(f"Error calculate DNA weight: {e}")

#CpG Island forecast
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error calculate DNA weight: {e}") from e
def predict_cpg(sequence: str) -> str:
    '''
    The CpG island prediction tool can predict potential CpG islands using the Gardiner Garden and Frommer (1987) method The calculation method is to use a 200bp window, with each shift of 1 bp. The CpG island is defined as an Obs/Exp value greater than 0.6 and a GC content greater than 50%. The calculation method for the number of CpG dimers in a window is to multiply the base number of 'C' in the window by the base number of 'G' in the window and then divide by the window length. CpG islands are typically found in the 5 'region of vertebrate genes.

    Args:
        sequence: DNA sequence.
    Returns:
        str: The Markdown content with CpG island.
    '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '').replace('"Untitled"', '')
        data = {
            "sr": "cpg",
            "sq": cleaned_sequence,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'predict_cpg')
        result = data_list[1]

        markdown = f'''
***CpG Island Prediction***
input sequence: {cleaned_sequence}

**Results**
'''
        result = result.replace('<div class="info">', '').replace('</div>', '\n').replace('<br /><br />', '\n')
        markdown += result
        return markdown
    except Exception as e:
        logging.error(f"Error predict CpG island: {e}")

# Properties and properties of PCR primers
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error predict CpG island: {e}") from e
def compute_primer_properties(sequence: str) -> str:
    '''
    This tool calculate the properties of PCR primer based on sequence.
    Args:
        sequence: DNA sequence.
        You should input as: 'arkbdctymvhu.garkbdctymvhu'
        You should use '.' to separate different sequences.
    Returns:
        str: The Markdown content with properties.
    '''
    try:
        cleaned_sequence = sequence.replace(' ', '').replace('\n', '')
        sequence_list = cleaned_sequence.split('.')
        fasta = ''
        for i, item in enumerate(sequence_list):
            name = f"sequence{i}"
            fasta += f">{name}\n{item}\n"
        data = {
            "sr": "primerstat",
            "sq": fasta,

        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'compute_primer_properties')
        result = data_list[1]
        result = result.replace('<br />', '').replace('<br/>', '\n')
        markdown = f'''
***PCR Primer Properties***
input sequence:
{fasta}

**Results**
{result}
'''
        return markdown
    except Exception as e:
        logging.error(f"Error calculate PCR primer properties: {e}")


# Protein amino acid statistics summary
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error calculate PCR primer properties: {e}") from e
def count_amino_acid(protein: str) -> str:
    '''
    This tool count the number of amino acids in the protein. Protein statistics summary: Based on the input protein sequence, count the number of each amino acid and calculate the proportion, which can quickly compare different sequences.

    Args:
        protein: protein sequence.
    Returns:
        str: The Markdown content with amino acid count.
    '''
    try:
        cleaned_protein = protein.replace(' ', '').replace('\n', '')
        data = {
            "sr": "prostats",
            "sq": cleaned_protein,
        }

        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'count_amino_acid')
        result = data_list[1]
        result = result.replace('<tr><td>', '').replace('</td><td>', ' \t\t\t').replace('</td></tr>', '\n').replace('<div class="info">', '').replace('</div><table border="1" width="100%" cellspacing="0" cellpadding="2"><tbody><tr><td class="title">Pattern:</td><td class="title">Times found:</td><td class="title">Percentage:\n<br />', '').replace('"Untitled" ','')
        result = result.replace('</tbody></table><br />\n<br /><br />\n<br /><br />','')
        markdown = f'''
***Amino Acid Statistics***
input sequence: {cleaned_protein}

**Results**
Amino Acid\tCount\tPercentage
{result}
'''
        return markdown

    except Exception as e:
        logging.error(f"Error count amino acid: {e}")


#Summary of enzyme restriction sites
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error count amino acid: {e}") from e
def summary_enzyme_cleavage_sites(sequence_type: str) -> str:
    '''
    The enzyme digestion site summary tool counts the number and location of commonly used restriction endonucleating recognition sites in DNA sequences.
    Args:
        sequence_enzyme: DNA sequence and type(linear of circular)
        You should use '.' to separate sequence and type.
        You should input as: 'garkbdctymvhu.linear'
    Returns:
        str: The Markdown content with enzyme cleavage sites.
    '''
    try:
        cleaned_sequence = sequence_type.replace(' ', '').replace('\n', '')
        sequence, type = cleaned_sequence.split('.')
        fasta= f">sequence\n{sequence}"
        data = {
            "sr": "restsumary",
            "sq": fasta,
            "top": type,
        }
        response = send_novopro_request(data)
        data_list = _novopro_result(response, 'summary_enzyme_cleavage_sites')
        result = data_list[1]

        h = html2text.HTML2Text()
        markdown_content = h.handle(result)
        markdown = f'''
***Summary Enzyme Cleavage Sites***
input sequence:
{fasta}

**Results**
'''
        markdown += markdown_content.replace('cuts once  \ncuts twice  \n', '')
        return markdown
    except Exception as e:
        logging.error(f"Error summary enzyme cleavage sites: {e}")


# Random DNA generation
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error summary enzyme cleavage sites: {e}") from e
def generate_random_DNA(length: int) -> str:
    '''
    This tool generate random DNA sequence.
    Args:
        length(integer): DNA length. You should input interger dierectly.
    Returns:
        str: The Markdown content with random DNA sequence.
    '''
    try:

        data = {
            "sr": "randdna",
            "seqlen": length,
            "seqnum": "1",
        }
        reponse = send_novopro_request(data)
        data_list = json.loads(reponse)
        if data_list[0] == "0":
            return "Fail to generate DNA sequence."
        result = data_list[1].replace('&gt;', '').replace('\n', '').replace('<br \/>', '').replace('<br />', '')
        useless, useful = result.split('.')

        markdown = f'''{useful}'''
        return markdown
    except Exception as e:
        logging.error(f"Error generate random DNA: {e}")



# if __name__ == "__main__":
#     # prompt = "hello"
#     sequence = "MGQPGNGSAFLLAPNGSHAPDHDVTQERDEVWVVGMGIVMSLIVLAIVFGNVLVITAIAKFERLQTVTNYFITSLACADLVMGLAVVPFGAAHILMKMWTFGNFWCEFWTSIDVLCVTASIETLCVIAVDRYFAITSPFKYQSLLTKNKARVIILMVWIVSGLTSFLPIQMHWYRATHQEAINCYANETCCDFFTNQAYAIASSIVSFYVPLVIMVFVYSRVFQEAKRQLQKIDKSEGRFHVQNLSQVEQDGRTGHGLRRSSKFCLKEHKALKTLGIIMGGNGYSSNGNTGEQSGYHVEQEKENKLLCEDLPGTEDFVGHQGTVPSDNIDSQGRNCSTNDSLL"
#     sequence2 = "MGQPGNGSAFLLAPNGSHAPDHDVTQERDEVWVVGMGIVMSLIVLAIVFGNVLVIT"
#     output = align_double_sequence(sequence,sequence2)
#     print(output)
    
        # Surface the failure instead of falling through to an implicit None.
        raise RuntimeError(f"Error generate random DNA: {e}") from e
