---
license: apache-2.0
---
# ProteinForceGPT: Generative strategies for modeling, design and analysis of protein mechanics


### Basic information

This protein language model is a 454M parameter autoregressive transformer model in GPT-style, trained to analyze and predict the mechanical properties of a large number of protein sequences. The model has both forward and inverse capabilities. For instance, using generate tasks, the model can design novel proteins that meet one or more mechanical constraints. 

This protein language foundation model was based on the NeoGPT-X architecture and uses rotary positional embeddings (RoPE). It has 16 attention heads, 36 hidden layers and a hidden size of 1024, an intermediate size of 4096 and uses a GeLU activation function. 

The pretraining task is defined as "Sequence<...>" where ... is an amino acid sequence.

Pretraining dataset: https://huggingface.co/datasets/lamm-mit/GPTProteinPretrained 
Pretrained model: https://huggingface.co/lamm-mit/GPTProteinPretrained

In this fine-tuned model, mechanics-related forward and inverse tasks are:

```raw
CalculateForce<GEECDCGSPSNP..>, 
CalculateEnergy<GEECDCGSPSNP..> 
CalculateForceEnergy<GEECDCGSPSNP...>
CalculateForceHistory<GEECDCGSPSNP...> 
GenerateForce<0.262> 
GenerateForce<0.220> 
GenerateForceEnergy<0.262,0.220> 
GenerateForceHistory<0.004,0.034,0.125,0.142,0.159,0.102,0.079,0.073,0.131,0.105,0.071,0.058,0.072,0.060,0.049,0.114,0.122,0.108,0.173,0.192,0.208,0.153,0.212,0.222,0.244>
```

### Load model

You can load the model using this code.

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

ForceGPT_model_name='lamm-mit/ProteinForceGPT'

tokenizer = AutoTokenizer.from_pretrained(ForceGPT_model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    ForceGPT_model_name, 
    trust_remote_code=True
).to(device)

model.config.use_cache = False
```

### Inference

Sample inference using the "Sequence<...>" task, where here, the model will simply autocomplete the sequence starting with "AIIAA":

```python
prompt = "Sequence<GEECDC"
generated = torch.tensor(tokenizer.encode(prompt, add_special_tokens = False)) .unsqueeze(0).to(device)
print(generated.shape, generated)

sample_outputs = model.generate(
                                inputs=generated, 
                                eos_token_id =tokenizer.eos_token_id,
                                do_sample=True,   
                                top_k=500, 
                                max_length = 300,
                                top_p=0.9, 
                                num_return_sequences=1,
                                temperature=1,
                                ).to(device)

for i, sample_output in enumerate(sample_outputs):
      print("{}: {}\n\n".format(i, tokenizer.decode(sample_output, skip_special_tokens=True)))
```
Sample inference using the "CalculateForce<...>" task, where here, the model will calculate the maximum unfolding force of a given sequence:

```python
prompt = "'CalculateForce<GEECDCGSPSNPCCDAATCKLRPGAQCADGLCCDQCRFKKKRTICRIARGDFPDDRCTGQSADCPRWN>"
generated = torch.tensor(tokenizer.encode(prompt, add_special_tokens = False)) .unsqueeze(0).to(device)

sample_outputs = model.generate(
                                inputs=generated, 
                                eos_token_id =tokenizer.eos_token_id,
                                do_sample=True,   
                                top_k=500, 
                                max_length = 300,
                                top_p=0.9, 
                                num_return_sequences=3,
                                temperature=1,
                                ).to(device)

for i, sample_output in enumerate(sample_outputs):
      print("{}: {}\n\n".format(i, tokenizer.decode(sample_output, skip_special_tokens=True)))
```
Output:
```raw
0: CalculateForce<GEECDCGSPSNPCCDAATCKLRPGAQCADGLCCDQCRFKKKRTICRIARGDFPDDRCTGQSADCPRWN> [0.262]```
```

## Citations
To cite this work:
```
@article{GhafarollahiBuehler_2024,
    title   = {ProtAgents: Protein discovery via large language model multi-agent collaborations combining physics and machine learning },
    author  = {A. Ghafarollahi, M.J. Buehler},
    journal = {},
    year    = {2024},
    volume  = {},
    pages   = {},
    url     = {}
}
```

The dataset used to fine-tune the model is available at:

```
@article{GhafarollahiBuehler_2024,
    title   = {ForceGen: End-to-end de novo protein generation based on nonlinear mechanical unfolding responses using a protein language diffusion model},
    author  = {B. Ni, D.L. Kaplan, M.J. Buehler},
    journal = {Science Advances},
    year    = {2024},
    volume  = {},
    pages   = {},
    url     = {}
}
```
