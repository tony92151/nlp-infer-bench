# Auto-Inference Framework Makefile

# Configuration variables
MODELS := bert-base-uncased microsoft/deberta-base answerdotai/ModernBERT-base
MODEL_NAMES := bert-base-uncased deberta-base modernbert-base
S3_BUCKET := inference-models-bucket
LOCAL_MODELS_DIR := models

# Default target
.PHONY: all download convert sync clean help

all: download convert

help:
	@echo "Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  setup           - Install dependencies with Optimum CLI support"
	@echo "  setup-all       - Install all dependencies (optimum + dev)"
	@echo "  setup-dev       - Install development dependencies"
	@echo ""
	@echo "Download:"
	@echo "  download        - Download all original models using huggingface-cli"
	@echo ""
	@echo "Convert:"
	@echo "  convert         - Convert all models using Optimum CLI"
	@echo "  all             - Complete workflow (download + convert)"
	@echo ""
	@echo "Storage:"
	@echo "  sync            - Sync to S3 using aws s3 sync"
	@echo "  clean           - Clean local model files"
	@echo "  status          - Check local model status"
	@echo ""
	@echo "Individual Models:"
	@echo "  quick-bert      - Complete BERT workflow"
	@echo "  quick-deberta   - Complete DeBERTa workflow"
	@echo "  quick-modernbert - Complete ModernBERT workflow"

# Install dependencies with Optimum support
setup:
	uv sync --extra optimum

# Install all dependencies (optimum + dev)
setup-all:
	uv sync --extra all

# Install for development
setup-dev:
	uv sync --extra dev

# Download all original models
download:
	@echo "Downloading original models using huggingface-cli..."
	huggingface-cli download bert-base-uncased --local-dir $(LOCAL_MODELS_DIR)/bert-base-uncased/pytorch --local-dir-use-symlinks False
	huggingface-cli download microsoft/deberta-base --local-dir $(LOCAL_MODELS_DIR)/deberta-base/pytorch --local-dir-use-symlinks False
	huggingface-cli download answerdotai/ModernBERT-base --local-dir $(LOCAL_MODELS_DIR)/modernbert-base/pytorch --local-dir-use-symlinks False

# Download specific models
download-bert:
	huggingface-cli download bert-base-uncased --local-dir $(LOCAL_MODELS_DIR)/bert-base-uncased/pytorch --local-dir-use-symlinks False

download-deberta:
	huggingface-cli download microsoft/deberta-base --local-dir $(LOCAL_MODELS_DIR)/deberta-base/pytorch --local-dir-use-symlinks False

download-modernbert:
	huggingface-cli download answerdotai/ModernBERT-base --local-dir $(LOCAL_MODELS_DIR)/modernbert-base/pytorch --local-dir-use-symlinks False

# Convert all models using Optimum CLI
convert:
	@echo "Converting model formats using Optimum CLI..."
	python scripts/convert_models.py --model all --format onnx --output-dir $(LOCAL_MODELS_DIR)
	python scripts/convert_models.py --model all --format openvino --output-dir $(LOCAL_MODELS_DIR)

# Convert specific models
convert-bert:
	python scripts/convert_models.py --model bert-base-uncased --format onnx --output-dir $(LOCAL_MODELS_DIR)/bert-base-uncased
	python scripts/convert_models.py --model bert-base-uncased --format openvino --output-dir $(LOCAL_MODELS_DIR)/bert-base-uncased

convert-deberta:
	python scripts/convert_models.py --model deberta-base --format onnx --output-dir $(LOCAL_MODELS_DIR)/deberta-base
	python scripts/convert_models.py --model deberta-base --format openvino --output-dir $(LOCAL_MODELS_DIR)/deberta-base

convert-modernbert:
	python scripts/convert_models.py --model modernbert-base --format onnx --output-dir $(LOCAL_MODELS_DIR)/modernbert-base
	python scripts/convert_models.py --model modernbert-base --format openvino --output-dir $(LOCAL_MODELS_DIR)/modernbert-base

# Sync to S3 using aws s3 sync
sync:
	@echo "Syncing to S3..."
	aws s3 sync $(LOCAL_MODELS_DIR)/ s3://$(S3_BUCKET)/models/ --delete

# Upload only, don't delete extra files on S3
upload:
	@echo "Uploading to S3..."
	aws s3 sync $(LOCAL_MODELS_DIR)/ s3://$(S3_BUCKET)/models/

# Clean local files
clean:
	@echo "Cleaning local model files..."
	rm -rf $(LOCAL_MODELS_DIR)

# Check model status
status:
	@echo "Local model status:"
	@for model in $(MODEL_NAMES); do \
		echo "$$model:"; \
		for format in pytorch onnx openvino; do \
			if [ -d "$(LOCAL_MODELS_DIR)/$$model/$$format" ]; then \
				echo "  $$format: ✓"; \
			else \
				echo "  $$format: ✗"; \
			fi; \
		done; \
	done

# Quick start - complete workflow for individual models
quick-bert:
	make download-bert
	make convert-bert
	@echo "BERT model ready! Use 'make sync' to upload to S3"

quick-deberta:
	make download-deberta
	make convert-deberta
	@echo "DeBERTa model ready! Use 'make sync' to upload to S3"

quick-modernbert:
	make download-modernbert
	make convert-modernbert
	@echo "ModernBERT model ready! Use 'make sync' to upload to S3"

# Verify S3 sync status
check-s3:
	@echo "Checking S3 status..."
	aws s3 ls s3://$(S3_BUCKET)/models/ --recursive --human-readable