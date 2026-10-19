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

tokenizer = T5Tokenizer.from_pretrained("QizhiPei/biot5-base-text2mol", model_max_length=512)
model = T5ForConditionalGeneration.from_pretrained('QizhiPei/biot5-base-text2mol')

task_definition = 'Definition: You are given a molecule description in English. Your job is to generate the molecule SELFIES that fits the description.\n\n'
text_input = 'The molecule is a monocarboxylic acid anion obtained by deprotonation of the carboxy and sulfino groups of 3-sulfinopropionic acid. Major microspecies at pH 7.3 It is an organosulfinate oxoanion and a monocarboxylic acid anion. It is a conjugate base of a 3-sulfinopropionic acid.'
task_input = f'Now complete the following example -\nInput: {text_input}\nOutput: '

model_input = task_definition + task_input
input_ids = tokenizer(model_input, return_tensors="pt").input_ids

generation_config = model.generation_config
generation_config.max_length = 512
generation_config.num_beams = 1

outputs = model.generate(input_ids, generation_config=generation_config)
output_selfies = tokenizer.decode(outputs[0], skip_special_tokens=True).replace(' ', '')
print(output_selfies)

import selfies as sf
output_smiles = sf.decoder(output_selfies)
print(output_smiles)
```

## References
For more information, please refer to our paper and GitHub repository.

Paper: [BioT5: Enriching Cross-modal Integration in Biology with Chemical Knowledge and Natural Language Associations](https://arxiv.org/abs/2310.07276)

GitHub: [BioT5](https://github.com/QizhiPei/BioT5)

Authors: *Qizhi Pei, Wei Zhang, Jinhua Zhu, Kehan Wu, Kaiyuan Gao, Lijun Wu, Yingce Xia, and Rui Yan* 