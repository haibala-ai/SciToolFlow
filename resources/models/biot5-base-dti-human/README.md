---
license: mit
datasets:
- QizhiPei/BioT5_finetune_dataset
language:
- en
---
## Example Usage
```python
from transformers import T5Tokenizer, T5ForConditionalGeneration

def add_prefix_to_amino_acids(protein_sequence):
    amino_acids = list(protein_sequence)
    prefixed_amino_acids = ['<p>' + aa for aa in amino_acids]
    new_sequence = ''.join(prefixed_amino_acids)
    return new_sequence

tokenizer = T5Tokenizer.from_pretrained("QizhiPei/biot5-base-dti-human", model_max_length=512)
model = T5ForConditionalGeneration.from_pretrained('QizhiPei/biot5-base-dti-human')

task_definition = 'Definition: Drug target interaction prediction task (a binary classification task) for the human dataset. If the given molecule and protein can interact with each other, indicate via "Yes". Otherwise, response via "No".\n\n'
selfies_input = '[C][/C][=C][Branch1][C][\\C][C][=Branch1][C][=O][O]'
protein_input = 'MQALRVSQALIRSFSSTARNRFQNRVREKQKLFQEDNDIPLYLKGGIVDNILYRVTMTLCLGGTVYSLYSLGWASFPRN'
protein_input = add_prefix_to_amino_acids(protein_input)
task_input = f'Now complete the following example -\nInput: Molecule: <bom>{selfies_input}<eom>\nProtein: <bop>{protein_input}<eop>\nOutput: '

model_input = task_definition + task_input
input_ids = tokenizer(model_input, return_tensors="pt").input_ids

generation_config = model.generation_config
generation_config.max_length = 8
generation_config.num_beams = 1

outputs = model.generate(input_ids, generation_config=generation_config)

print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

## References
For more information, please refer to our paper and GitHub repository.

Paper: [BioT5: Enriching Cross-modal Integration in Biology with Chemical Knowledge and Natural Language Associations](https://arxiv.org/abs/2310.07276)

GitHub: [BioT5](https://github.com/QizhiPei/BioT5)

Authors: *Qizhi Pei, Wei Zhang, Jinhua Zhu, Kehan Wu, Kaiyuan Gao, Lijun Wu, Yingce Xia, and Rui Yan* 