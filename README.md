![](./cover.png)

A system for generating unique, stochastic and diverse outputs from LLMs while eliminating repetition and maximizing coverage of the output space.

## Problem Statement

Large Language Models suffer from repetitive outputs, missing the long tail of possibilities. Teams waste money on duplicates, manual deduplication, and shallow test coverage. **Uniqly** solves this by maximizing unique, relevant outputs per dollar spent.

## How It Works
<h3>Problem Formulation</h3>
<p>We have a base model <img src="https://i.upmath.me/svg/F" alt="F" /> that maps input <img src="https://i.upmath.me/svg/X" alt="X" /> to a distribution over output space <img src="https://i.upmath.me/svg/Y" alt="Y" /> with probability mass function <img src="https://i.upmath.me/svg/p(y%5Cmid%20x)" alt="p(y\mid x)" />. The model <img src="https://i.upmath.me/svg/F" alt="F" /> is stochastic and black-box.</p>
<p>At each step <img src="https://i.upmath.me/svg/t" alt="t" />, we want to select a subset <img src="https://i.upmath.me/svg/Y_t%3D%5C%7By%5E%7B(t)%7D_1%2C%5Cdots%2Cy%5E%7B(t)%7D_%7Bk_t%7D%5C%7D" alt="Y_t=\{y^{(t)}_1,\dots,y^{(t)}_{k_t}\}" /> with:</p>
<ul>
<li><strong>No repeats</strong> across all previous steps: <img src="https://i.upmath.me/svg/Y_t%20%5Ccap%20%5Cbigcup_%7Bi%3Ct%7D%20Y_i%3D%5Cvarnothing" alt="Y_t \cap \bigcup_{i&lt;t} Y_i=\varnothing" /></li>
<li><strong>High novelty</strong> and growing coverage of the output space <img src="https://i.upmath.me/svg/Y" alt="Y" /></li>
<li><strong>Submodular coverage</strong> maximization subject to non-repetition constraints</li>
</ul>
<h3>Objective Function</h3>
<p>We maximize a submodular coverage function:</p>
<p align="center"><img align="center" src="https://i.upmath.me/svg/%5Cmax_%7BY_%7B1%3AT%7D%7D%20%5C%3B%20%5Cmathcal%7BC%7D%5C!%5Cleft(%5Cbigcup_%7Bt%3D1%7D%5ET%20Y_t%5Cright)%20%5Cquad%5Ctext%7Bsubject%20to%7D%5Cquad%20Y_t%20%5Ccap%20%5Cbigcup_%7Bi%3Ct%7D%20Y_i%3D%5Cvarnothing" alt="\max_{Y_{1:T}} \; \mathcal{C}\!\left(\bigcup_{t=1}^T Y_t\right) \quad\text{subject to}\quad Y_t \cap \bigcup_{i&lt;t} Y_i=\varnothing" /></p>
<p>Where <img src="https://i.upmath.me/svg/%5Cmathcal%7BC%7D" alt="\mathcal{C}" /> represents cluster coverage, facility location, or rarity-weighted coverage bins.</p>
<h3>Implementation Approach</h3>
<p><strong>Current Implementation</strong> (OpenAI API):</p>
<ol>
<li><strong>High-Temperature Sampling</strong>: Use standard API with <code>temperature=1.2</code> and <code>top_p=0.95</code> for diversity</li>
<li><strong>Multi-Round Generation</strong>: Generate multiple batches with different seeds for breadth</li>
<li><strong>Hard Deduplication</strong>: Filter candidates using <img src="https://i.upmath.me/svg/%5Cmathbf%7B1%7D%5By%5Cnotin%20H%5D" alt="\mathbf{1}[y\notin H]" /> with canonicalized string matching</li>
<li><strong>MMR Reranking</strong>: Apply post-generation scoring:
<img src="https://i.upmath.me/svg/%5Ctext%7Bscore%7D%20%3D%20%5Clambda%20%5Ccdot%20%5Ctext%7Brelevance%7D%20-%20(1-%5Clambda)%20%5Ccdot%20%5Ctext%7Bsimilarity%5C_to%5C_history%7D%20%2B%20%5Calpha%20%5Ccdot%20%5Ctext%7Blogprob%7D%20%2B%20%5Cbeta%20%5Ccdot%20%5Ctext%7Brarity%7D" alt="\text{score} = \lambda \cdot \text{relevance} - (1-\lambda) \cdot \text{similarity\_to\_history} + \alpha \cdot \text{logprob} + \beta \cdot \text{rarity}" /></li>
<li><strong>Top-k Selection</strong>: Select highest scoring unique candidates</li>
</ol>
<p><strong>Future Implementation</strong> (Direct Sampling Control):
For providers supporting custom sampling, we could implement the ideal <strong>time-varying reweighted distribution</strong>:</p>
<p align="center"><img align="center" src="https://i.upmath.me/svg/%5Cpi_t(y)%20%5Cpropto%20%5Cmathbf%7B1%7D%5By%5Cnotin%20H%5D%20%5Ccdot%20p(y%5Cmid%20x)%5E%7B%5Calpha_t%7D%20%5Ccdot%20%5Cexp%5C!%5Cleft(-%5Clambda_t%20%5Cmax_%7Bs%5Cin%20H%7D%5Ctext%7Bsim%7D(y%2Cs)%20%2B%20%5Cbeta_t%20r_%7B%5Ctext%7Brare%7D%7D(y)%5Cright)" alt="\pi_t(y) \propto \mathbf{1}[y\notin H] \cdot p(y\mid x)^{\alpha_t} \cdot \exp\!\left(-\lambda_t \max_{s\in H}\text{sim}(y,s) + \beta_t r_{\text{rare}}(y)\right)" /></p>
<p>Then sample <img src="https://i.upmath.me/svg/k_t" alt="k_t" /> items <strong>without replacement</strong> using Gumbel-Top-k or k-DPP.</p>


## Key Features

- **Zero Repetition**: Hard deduplication across all generations
- **Intelligent Diversity**: Embedding-based similarity penalties push for novelty
- **Configurable Context**: Generate suggestions for any domain
- **FIFO + Random Access**: Consume outputs sequentially or sample randomly
- **Real-time Metrics**: Track generation rates, uniqueness, and coverage
- **Scalable**: Built on Celery + Redis for production workloads

## API Endpoints

### Core Operations
- `GET /next/{n}` - Get next n unique suggestions (FIFO)
- `GET /random/{n}` - Get n random suggestions from accumulated set
- `GET /peek/{n}` - Preview next suggestions without consuming
- `GET /status` - View generation stats and queue status

### Management
- `POST /generate` - Manually trigger generation
- `POST /configure` - Update context and generation settings
- `DELETE /clear` - Reset all suggestions and stats

## Getting Started

1. **Set Environment Variables**:
```bash
export OPENAI_API_KEY=your_key_here
export CONTEXT_X="your suggestion context (the X we use to generate)"
export REDIS_URL="redis://localhost:6379"
```

1. **Generate Suggestions**:
```bash
# Manually trigger generation
curl -X POST http://localhost:9812/generate

# Get next 5 unique suggestions
curl http://localhost:9812/next/5

# Get random samples
curl http://localhost:9812/random/10
```

## Configuration

### Environment Variables
- `CONTEXT_X`: What to generate suggestions for (e.g., "creative writing prompts")
- `CONTEXT_ID`: Unique identifier for this context (default: "default")
- `GENERATION_INTERVAL`: Seconds between automatic generations (default: 60)
- `MAX_QUEUE_SIZE`: Maximum suggestions to keep in queue (default: 1000)
- `MODEL_CHAT`: OpenAI model for generation (default: "gpt-4o-mini-2024-07-18")
- `MODEL_EMBED`: OpenAI model for embeddings (default: "text-embedding-3-small")

### Algorithm Parameters (in `llms.py`)
- `TARGET_K`: Unique ideas per generation round (default: 20)
- `TEMPERATURE`: Sampling temperature for diversity (default: 1.2)
- `MMR_LAMBDA`: Novelty vs relevance balance (default: 0.8)
- `ALPHA/BETA/LAM`: Weights for confidence, rarity, and diversity scoring

## Technical Details

### Deduplication Strategy
1. **Canonicalization**: Lowercase, normalize whitespace, strip punctuation
1. **Hash-based Storage**: Fast O(1) lookup in Redis sets
1. **Embedding Similarity**: Semantic deduplication using cosine distance
1. **Multi-round Sampling**: Generate multiple candidate batches
1. **Structured Outputs**: JSON schema ensures consistent format
1. **MMR Reranking**: Balance relevance to prompt vs novelty vs history
1. **Incremental Updates**: Add only truly unique items to persistent queue
1. **Logprob Confidence**: Model certainty in generations
1. **Rarity Bonus**: Boost underrepresented clusters
1. **Similarity Penalty**: Penalize near-duplicates to existing items

## Business Impact

- **Cost Efficiency**: Higher unique outputs per API dollar
- **Coverage**: Better long-tail exploration vs standard sampling
- **Automation**: Eliminates manual deduplication workflows
- **Scale**: Infinite generation without repetition fatigue

## Metrics Dashboard

The `/status` endpoint provides:
- Queue size and total unique suggestions
- Generation rate and last update timestamp
- Redis connection health
- Total items generated over time
