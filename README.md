![](./cover.png)

A system for generating unique, stochastic and diverse outputs from LLMs while eliminating repetition and maximizing coverage of the output space.

## Problem Statement

Large Language Models suffer from repetitive outputs, missing the long tail of possibilities. Teams waste money on duplicates, manual deduplication, and shallow test coverage. **Uniqly** solves this by maximizing unique, relevant outputs per dollar spent.

## How It Works

### Problem Formulation
We have a base model $F$ that maps input $X$ to a distribution over output space $Y$ with probability mass function $p(y\mid x)$. The model $F$ is stochastic and black-box.

At each step $t$, we want to select a subset $Y_t=\{y^{(t)}_1,\dots,y^{(t)}_{k_t}\}$ with:
- **No repeats** across all previous steps: $Y_t \cap \bigcup_{i<t} Y_i=\varnothing$
- **High novelty** and growing coverage of the output space $Y$
- **Submodular coverage** maximization subject to non-repetition constraints

### Objective Function
We maximize a submodular coverage function:

$$\max_{Y_{1:T}} \; \mathcal{C}\!\left(\bigcup_{t=1}^T Y_t\right) \quad\text{subject to}\quad Y_t \cap \bigcup_{i<t} Y_i=\varnothing$$

Where $\mathcal{C}$ represents cluster coverage, facility location, or rarity-weighted coverage bins.

### Implementation Approach

**Current Implementation** (OpenAI API):
1. **High-Temperature Sampling**: Use standard API with `temperature=1.2` and `top_p=0.95` for diversity
2. **Multi-Round Generation**: Generate multiple batches with different seeds for breadth
3. **Hard Deduplication**: Filter candidates using $\mathbf{1}[y\notin H]$ with canonicalized string matching
4. **MMR Reranking**: Apply post-generation scoring:
   $$\text{score} = \lambda \cdot \text{relevance} - (1-\lambda) \cdot \text{similarity\_to\_history} + \alpha \cdot \text{logprob} + \beta \cdot \text{rarity}$$
5. **Top-k Selection**: Select highest scoring unique candidates

**Future Implementation** (Direct Sampling Control):
For providers supporting custom sampling, we could implement the ideal **time-varying reweighted distribution**:

$$\pi_t(y) \propto \mathbf{1}[y\notin H] \cdot p(y\mid x)^{\alpha_t} \cdot \exp\!\left(-\lambda_t \max_{s\in H}\text{sim}(y,s) + \beta_t r_{\text{rare}}(y)\right)$$

Then sample $k_t$ items **without replacement** using Gumbel-Top-k or k-DPP.

### Core Algorithm
- **Multi-Round Generation**: Generate diverse candidate batches with varying seeds
- **Hard Deduplication**: Canonicalizes outputs and maintains persistent history $H$
- **MMR Reranking**: Applies Maximum Marginal Relevance with embedding-based diversity scoring
- **Structured Outputs**: Forces JSON schema compliance for consistent, parseable results


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
