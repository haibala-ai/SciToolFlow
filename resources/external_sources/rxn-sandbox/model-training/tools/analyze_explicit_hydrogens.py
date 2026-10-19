#!/usr/bin/env python3
"""
Script to analyze reactions with explicit hydrogens and check for organometallic elements.
Usage: python check_explicit_hydrogens.py <input_file>
"""

import sys
import re
from collections import Counter

# Common organometallic and metalloid elements
METALS = {
    'Li', 'Na', 'K', 'Mg', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 
    'Cu', 'Zn', 'Al', 'Ga', 'Ge', 'Sn', 'Pb', 'B', 'Si', 'P', 'Pd', 'Pt', 'Rh', 
    'Ru', 'Os', 'Ir', 'Au', 'Ag', 'Cd', 'Hg', 'Zr', 'Mo', 'W', 'Re', 'Bi'
}

def has_explicit_hydrogens(smiles):
    """Check if SMILES contains explicit hydrogens like [CH], [CH2], [CH3]"""
    return bool(re.search(r'\[CH\d?\]', smiles))

def extract_elements(smiles):
    """Extract all elements in square brackets from SMILES"""
    # Match elements in square brackets, including charges and other notation
    pattern = r'\[([A-Z][a-z]?)'
    elements = re.findall(pattern, smiles)
    return set(elements)

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_explicit_hydrogens.py <input_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    try:
        with open(input_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File {input_file} not found")
        sys.exit(1)
    
    # Skip header if present
    if lines and lines[0].strip().lower() in ['rxn', 'reaction', 'smiles']:
        lines = lines[1:]
    
    total_reactions = len(lines)
    reactions_with_explicit_h = []
    reactions_with_explicit_h_and_metals = []
    reactions_with_explicit_h_no_metals = []
    metal_counter = Counter()
    
    print("Analyzing reactions...")
    print("=" * 60)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if has_explicit_hydrogens(line):
            reactions_with_explicit_h.append(line)
            elements = extract_elements(line)
            metals_found = elements & METALS
            
            if metals_found:
                reactions_with_explicit_h_and_metals.append(line)
                for metal in metals_found:
                    metal_counter[metal] += 1
            else:
                reactions_with_explicit_h_no_metals.append(line)
    
    # Print statistics
    print(f"\nTotal reactions: {total_reactions}")
    print(f"Reactions with explicit hydrogens: {len(reactions_with_explicit_h)}")
    print(f"  - With organometallic elements: {len(reactions_with_explicit_h_and_metals)}")
    print(f"  - Without organometallic elements: {len(reactions_with_explicit_h_no_metals)}")
    
    if reactions_with_explicit_h:
        percentage = (len(reactions_with_explicit_h_and_metals) / len(reactions_with_explicit_h)) * 100
        print(f"\nPercentage with metals: {percentage:.2f}%")
    
    # Show metal breakdown
    if metal_counter:
        print("\nBreakdown by metal type (for reactions with explicit H):")
        print("=" * 60)
        for metal, count in metal_counter.most_common():
            print(f"  {metal}: {count} reactions")
    
    # Show examples without metals
    if reactions_with_explicit_h_no_metals:
        print(f"\nFirst 10 examples with explicit H but NO metals:")
        print("=" * 60)
        for i, rxn in enumerate(reactions_with_explicit_h_no_metals[:10], 1):
            # Truncate long reactions for display
            display_rxn = rxn if len(rxn) <= 100 else rxn[:97] + "..."
            print(f"{i}. {display_rxn}")
    
    # Additional analysis: check for specific patterns
    print("\n\nAdditional Analysis:")
    print("=" * 60)
    
    # Check for radicals (indicated by explicit H on single atoms)
    radical_pattern = r'\[CH?\](?![0-9])'  # [C] or [CH] not followed by a digit
    radicals = [rxn for rxn in reactions_with_explicit_h_no_metals if re.search(radical_pattern, rxn)]
    print(f"Potential radicals (no metals): {len(radicals)}")
    
    # Check for charged species
    charged_pattern = r'\[CH\d?[+-]\]'
    charged = [rxn for rxn in reactions_with_explicit_h_no_metals if re.search(charged_pattern, rxn)]
    print(f"Charged species with explicit H (no metals): {len(charged)}")
    
    if radicals and len(radicals) <= 5:
        print("\nExamples of potential radicals:")
        for rxn in radicals[:5]:
            display_rxn = rxn if len(rxn) <= 100 else rxn[:97] + "..."
            print(f"  {display_rxn}")

if __name__ == "__main__":
    main()

# Made with Bob
