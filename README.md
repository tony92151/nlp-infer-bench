# nlp-infer-bench

An experimental platform for comparing NLP model performance across different inference frameworks.

## Supported Models & Frameworks

**Models**: BERT, DeBERTa, ModernBERT  
**Frameworks**: PyTorch, ONNX Runtime, OpenVINO  
**Datasets**: IMDB, SST-2, AG News

## Quick Start

### Setup
```bash
# Install with Optimum CLI support
make setup

# Or install all dependencies (optimum + dev tools)
make setup-all

# Or install manually
uv sync --extra optimum

# Configure AWS
aws configure
```

### Workflow
```bash
make download       # Download models
make convert        # Convert using Optimum CLI
make sync           # Upload to S3

# Or complete workflow
make all            # download + convert
```

### Individual Models
```bash
make quick-bert     # Complete BERT workflow
make quick-deberta  # Complete DeBERTa workflow
make quick-modernbert # Complete ModernBERT workflow
```

## Directory Structure

```
nlp-infer-bench/
├── Makefile                 # Workflow commands
├── config/models.yaml       # Model configuration (simplified)
├── scripts/convert_models.py # Optimum CLI wrapper
└── models/                  # Local storage
    ├── bert-base-uncased/
    ├── deberta-base/
    └── modernbert-base/
```

## Available Commands

```bash
make help           # Show all commands
make download       # Download models
make convert        # Convert models
make sync           # Sync to S3
make status         # Check status
make clean          # Clean files
```

## What Changed

**Removed**: 660+ lines of custom conversion code  
**Added**: Single 165-line Optimum CLI wrapper  
**Result**: Simpler, more reliable, professionally optimized conversions

## Next Steps

1. Set up AWS Batch for experiments
2. Configure experiment parameters
3. Execute performance comparisons
4. Analyze results