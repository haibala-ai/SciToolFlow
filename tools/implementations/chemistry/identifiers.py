"""Auditable PubChem resolution and database-annotation queries."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def resolve_chemical_identifier(identifier: str, identifier_kind: str = "name",
                                outputs: list[str] | None = None,
                                record_policy: str = "unique") -> dict:
    """Resolve a name, SMILES, InChI, InChIKey or CID through PubChem with provenance.

    outputs may contain smiles, inchi, inchikey, mol and cas (default smiles/inchi).
    No fragment removal, neutralization or tautomer normalization is applied.
    record_policy=unique rejects multiple returned records; first explicitly
    chooses the first; all returns up to 100 and fails rather than silently
    truncating. CAS returns all strings under PubChem's CAS section, without a
    first-CAS or legal-identity claim. MOL uses the selected CID's 2D SDF record.
    Missing records/fields, bad inputs and upstream failures raise explicit errors.
    """
    from rdkit import Chem
    from tools.implementations.shared.pubchem import get, smiles_property
    if identifier_kind not in {"name", "smiles", "inchi", "inchikey", "cid"}:
        raise ValueError("identifier_kind must be name, smiles, inchi, inchikey, or cid")
    if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 10000:
        raise ValueError("identifier must be a nonempty string of at most 10000 characters")
    if record_policy not in {"unique", "first", "all"}:
        raise ValueError("record_policy must be unique, first, or all")
    outputs = ["smiles", "inchi"] if outputs is None else outputs
    if not isinstance(outputs, list) or not outputs or len(set(outputs)) != len(outputs) or any(o not in {"smiles", "inchi", "inchikey", "mol", "cas"} for o in outputs):
        raise ValueError("outputs must be a nonempty unique list of smiles/inchi/inchikey/mol/cas")
    if identifier_kind == "smiles":
        from .core import molecule
        molecule(identifier)
    if identifier_kind == "cid" and (not identifier.isdigit() or int(identifier) <= 0):
        raise ValueError("CID must be a positive decimal identifier string")
    endpoint = f"rest/pug/compound/{identifier_kind}/{quote(identifier.strip(), safe='')}/property/SMILES,InChI,InChIKey/JSON"
    response = get(endpoint)
    records = response.json().get("PropertyTable", {}).get("Properties")
    if not isinstance(records, list) or not records:
        raise ValueError("PubChem returned no compound property records")
    if len(records) > 100:
        raise ValueError("PubChem returned more than 100 records; resolve a more specific identifier")
    if record_policy == "unique" and len(records) != 1:
        raise ValueError(f"Identifier resolved to {len(records)} records; specify first/all or use a CID")
    selected = records[:1] if record_policy == "first" else records
    results = []
    for record in selected:
        cid = record.get("CID")
        if type(cid) is not int or cid <= 0:
            raise ValueError("PubChem returned an invalid CID")
        row = {"cid": cid}
        for output in outputs:
            if output == "smiles":
                row[output] = smiles_property(record)
            elif output in {"inchi", "inchikey"}:
                key = "InChI" if output == "inchi" else "InChIKey"
                if not isinstance(record.get(key), str) or not record[key]:
                    raise ValueError("PubChem record lacks " + key)
                row[output] = record[key]
            elif output == "mol":
                sdf = get(f"rest/pug/compound/cid/{cid}/SDF", params={"record_type": "2d"})
                mol = Chem.MolFromMolBlock(sdf.text.split("$$$$")[0], removeHs=False)
                if mol is None:
                    raise ValueError("PubChem returned an invalid MOL record")
                row[output] = Chem.MolToMolBlock(mol)
                row["mol_source"] = {"url": sdf.url, "sha256": hashlib.sha256(sdf.content).hexdigest()}
            else:
                data = get(f"rest/pug_view/data/compound/{cid}/JSON")
                values = set()
                def visit(section):
                    if section.get("TOCHeading") == "CAS":
                        for info in section.get("Information", []):
                            for value in info.get("Value", {}).get("StringWithMarkup", []):
                                text = value.get("String")
                                if isinstance(text, str) and text:
                                    values.add(text)
                    for child in section.get("Section", []):
                        visit(child)
                for section in data.json().get("Record", {}).get("Section", []):
                    visit(section)
                row["cas"] = sorted(values)
                row["cas_status"] = "reported" if values else "no_CAS_section_values"
                row["cas_source"] = {"url": data.url, "sha256": hashlib.sha256(data.content).hexdigest()}
        results.append(row)
    return {"identifier": identifier, "identifier_kind": identifier_kind,
            "record_policy": record_policy, "returned_record_count": len(results),
            "observed_match_count": len(records), "records": results,
            "provenance": {"provider": "PubChem", "url": response.url,
                           "fetched_at": datetime.now(timezone.utc).isoformat(),
                           "response_sha256": hashlib.sha256(response.content).hexdigest()},
            "normalization": "No local normalization; PubChem database representations retained and provider standardization may apply"}


def query_molecule_catalog(smiles: str, catalog: str = "zinc-instock-mini") -> dict:
    """Query a local molbloom Bloom filter for probabilistic database membership.

    This is neither a patent nor current purchasability determination. The bundled
    zinc-instock-mini catalog has a documented false-positive rate of 0.07 and
    dated source content. Other installed cached catalogs may be selected; absent
    filters raise an error and are never downloaded implicitly. Canonical SMILES
    are used for lookup; true means probably present, false means absent from that
    particular filter under its canonicalization convention.
    """
    import molbloom
    from rdkit import Chem
    from .core import molecule
    catalogs = molbloom.catalogs()
    if catalog not in catalogs:
        raise ValueError("Unknown molbloom catalog: " + str(catalog))
    if catalog != "zinc-instock-mini" and not (Path.home() / ".cache/molbloom" / (catalog + ".bloom")).is_file():
        raise FileNotFoundError("Catalog is not installed locally; install the genuine filter explicitly: " + catalog)
    canonical = Chem.MolToSmiles(molecule(smiles, "remove"))
    present = bool(molbloom.buy(canonical, catalog=catalog, canonicalize=False))
    return {"catalog": catalog, "catalog_description": catalogs[catalog],
            "canonical_smiles": canonical, "probably_present": present,
            "interpretation": "probabilistic membership of the named dated catalog; not a legal patent or live stock claim",
            "molbloom_version": molbloom.__version__}


def pubchem_safety(identifier: str) -> dict:
    """Return source safety sections and structured GHS icon annotations from PubChem.

    identifier is a PubChem-resolvable name or CAS string. No LLM interpretation,
    hazard prediction or absence-of-hazard claim. GHS icon labels and the reported
    explosive-icon flag come from the same retrieved record. Missing annotations
    remain missing; an absent pictogram does not establish an absent hazard.
    """
    from tools.implementations.shared.pubchem import get
    if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 1000:
        raise ValueError("identifier must contain 1-1000 characters")
    found = get("rest/pug/compound/name/" + quote(identifier.strip(), safe="") + "/cids/JSON")
    cids = found.json().get("IdentifierList", {}).get("CID")
    if not isinstance(cids, list) or len(cids) != 1:
        raise ValueError("Safety identifier must resolve to one CID; use a more specific name/CAS")
    response = get(f"rest/pug_view/data/compound/{cids[0]}/JSON")
    sections, labels = [], set()
    wanted = {"Safety and Hazards", "Toxicity", "Chemical Safety"}
    def visit(section, within_ghs=False):
        heading = section.get("TOCHeading")
        if heading in wanted:
            sections.append(section)
        ghs = within_ghs or heading in {"Chemical Safety", "GHS Classification"}
        if ghs:
            for info in section.get("Information", []):
                for value in info.get("Value", {}).get("StringWithMarkup", []):
                    for mark in value.get("Markup", []):
                        if mark.get("Type") == "Icon" and mark.get("Extra"):
                            labels.add(str(mark["Extra"]))
        for child in section.get("Section", []):
            visit(child, ghs)
    for section in response.json().get("Record", {}).get("Section", []):
        visit(section)
    if not sections and not labels:
        raise ValueError("PubChem record has no selected safety sections or GHS icon labels")
    return {"identifier": identifier, "cid": cids[0], "sections": sections,
            "ghs_icon_labels": sorted(labels),
            "explosive_icon_reported": any("explos" in value.lower() for value in labels),
            "interpretation": "Database annotations only; absent labels are not evidence of absent hazard.",
            "provenance": {"provider": "PubChem", "url": response.url,
                           "fetched_at": datetime.now(timezone.utc).isoformat(),
                           "response_sha256": hashlib.sha256(response.content).hexdigest()}}
