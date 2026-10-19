COMMON_SOLVENT_SMILES = {
    "O",                    # water
    "CS(=O)C",              # DMSO
    "CC#N",                 # acetonitrile
    "CO",                   # methanol
    "CCO",                  # ethanol
    "CC(C)O",               # isopropanol
    "C[N+](=O)[O-]",        # nitromethane
    "CN(C)C=O",             # DMF
    "CN(C)C(C)=O",          # DMA
    "O=C1N(CCCN1)C",        # NMP
    "OCCO",                 # ethylene glycol
    "NC=O",                 # formamide
    "O=S1(=O)CCCC1",        # sulfolane
    "COCCO",                # 2-methoxyethanol
    "CC(=O)C",              # acetone
    "C1CCOC1",              # THF
    "O1CCOCC1",             # dioxane
    "ClCCl",                # DCM
    "ClC(Cl)Cl",            # chloroform
    "ClCCCl",               # 1,2-dichloroethane
    "COC(=O)OC",            # dimethyl carbonate
    "COc1ccccc1",           # anisole
    "CCOC(=O)C",            # ethyl acetate
    "CCOCC",                # diethyl ether
    "Cc1ccccc1",            # toluene
    "Cc1ccccc1C",           # o-xylene
    "Cc1cccc(C)c1",         # m-xylene
    "Cc1ccc(C)cc1",         # p-xylene
    "Cc1cc(C)cc(C)c1",      # mesitylene
    "ClC(Cl)(Cl)Cl",        # carbon tetrachloride
    "C1CCCCC1",             # cyclohexane
    "CCCCCC",               # n-hexane
    "CCCCCCC",              # heptane
    "CCCCC",                # pentane
    "c1ccccc1",             # benzene
}

INERT_ATMOSPHERE_GASES = {
    "N#N",   # nitrogen
    "[Ar]",  # argon (rare but possible)
}

REACTIVE_GASES = {
    "O=O",      # oxygen
    "[H][H]",   # hydrogen
}

COMMON_ION_SMILES = {
    "[Cl-]",
    "[Br-]",
    "[I-]",
    "[F-]",
    "[NH4+]",
    "[Na+]",
    "[K+]",
    "[Li+]",
}

COMMON_ELEMENTAL_SPECTATORS = {
    "Cl",        # chlorine artefact
    "[Cl]",      # sometimes appears bracketed
    "Br",
    "[Br]",
    "I",
    "[I]",
    "[Mg]",
    "Mg",
    "[Zn]",
    "Zn",
    "[Cu]",
    "Cu",
    "[Fe]",
    "Fe",
    "[Pd]",
}

COMMON_HALOGEN_SMILES = {
    "ClCl",   # Cl2
    "BrBr",   # Br2
    "II",     # I2  (non-standard but common in datasets)
}


def is_solvent(smiles: str) -> bool:
    return smiles in COMMON_SOLVENT_SMILES


def is_gas(smiles: str) -> bool:
    return smiles in INERT_ATMOSPHERE_GASES or smiles in REACTIVE_GASES


def is_ion(smiles: str) -> bool:
    return smiles in COMMON_ION_SMILES


def is_halogen(smiles: str) -> bool:
    return smiles in COMMON_HALOGEN_SMILES


# Checks if the SMILES belongs to a spectator that shouldn't be expanded via retrosynthesis
def is_spectator(smiles: str) -> bool:
    return (
        is_solvent(smiles)
        or is_gas(smiles)
        or is_ion(smiles)
        or is_halogen(smiles)
        or smiles in COMMON_ELEMENTAL_SPECTATORS
    )


# Strips spectators that do not generate unique reactions
def strip_neutral_spectators(reactants: list[str]) -> list[str]:
    return sorted(
        r for r in reactants
        if not is_solvent(r) and r not in INERT_ATMOSPHERE_GASES
    )
