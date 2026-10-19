
input_file = 'reactions.txt'
output_file = 'reactions_cleaned.txt'

with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
    for line in infile:
        cleaned_line = line.split('|')[0].strip()
        outfile.write(cleaned_line + '\n')

print(f"Cleaned SMILES reactions saved to '{output_file}'")
