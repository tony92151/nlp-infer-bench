#!/usr/bin/env python3
"""
Simplified model conversion script using Optimum CLI
Replaces all custom conversion logic with Hugging Face Optimum
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any
import yaml

class OptimumModelConverter:
    """Simplified model converter using Optimum CLI"""
    
    def __init__(self, config_path: str = "config/models.yaml"):
        """Initialize converter with configuration"""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load model configuration"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def convert_model(self, model_name: str, target_format: str, output_dir: str) -> bool:
        """
        Convert model using Optimum CLI
        
        Args:
            model_name: Model name from config
            target_format: Target format (onnx, openvino)
            output_dir: Output directory
            
        Returns:
            bool: Success status
        """
        try:
            # Get model configuration
            if model_name not in self.config['models']:
                raise ValueError(f"Model {model_name} not found in configuration")
            
            model_config = self.config['models'][model_name]
            model_source = model_config['source']
            task = model_config['task']
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Build optimum-cli command
            cmd = [
                "optimum-cli", "export", target_format,
                "--model", model_source,
                "--task", task,
                output_dir
            ]
            
            # Add format-specific options
            if target_format == "onnx":
                cmd.extend(self._get_onnx_options(model_config))
            elif target_format == "openvino":
                cmd.extend(self._get_openvino_options(model_config))
            
            # Execute conversion
            self.logger.info(f"Converting {model_name} to {target_format}")
            self.logger.info(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            self.logger.info(f"Successfully converted {model_name} to {target_format}")
            self.logger.debug(f"Output: {result.stdout}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Conversion failed for {model_name}: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Error converting {model_name}: {str(e)}")
            return False
    
    def _get_onnx_options(self, model_config: Dict[str, Any]) -> List[str]:
        """Get ONNX-specific conversion options"""
        options = []
        
        # Add opset version if specified
        if 'optimization' in model_config and 'onnx' in model_config['optimization']:
            onnx_config = model_config['optimization']['onnx']
            if 'opset_version' in onnx_config:
                options.extend(["--opset", str(onnx_config['opset_version'])])
        
        return options
    
    def _get_openvino_options(self, model_config: Dict[str, Any]) -> List[str]:
        """Get OpenVINO-specific conversion options"""
        options = []
        
        # Add precision options if specified
        if 'optimization' in model_config and 'openvino' in model_config['optimization']:
            openvino_config = model_config['optimization']['openvino']
            if openvino_config.get('precision') == 'FP16':
                options.extend(["--fp16"])
        
        return options
    
    def convert_all_models(self, target_format: str, base_output_dir: str) -> Dict[str, bool]:
        """
        Convert all configured models to specified format
        
        Args:
            target_format: Target format (onnx, openvino)
            base_output_dir: Base output directory
            
        Returns:
            Dict mapping model names to success status
        """
        results = {}
        
        for model_name in self.config['models']:
            output_dir = os.path.join(base_output_dir, model_name, target_format)
            success = self.convert_model(model_name, target_format, output_dir)
            results[model_name] = success
            
        return results
    
    def validate_dependencies(self) -> bool:
        """Check if required dependencies are installed"""
        try:
            # Check if optimum-cli is available
            result = subprocess.run(
                ["optimum-cli", "--help"], 
                capture_output=True, 
                check=True
            )
            self.logger.info("Optimum CLI is available")
            return True
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("Optimum CLI not found. Please install with: pip install optimum[onnxruntime,openvino]")
            return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Simplified model conversion using Optimum CLI")
    parser.add_argument('--model', type=str, 
                       help='Model name (from config) or "all" for all models')
    parser.add_argument('--format', type=str, required=True,
                       choices=['onnx', 'openvino'], 
                       help='Target format')
    parser.add_argument('--output-dir', type=str, required=True,
                       help='Output directory')
    parser.add_argument('--config', type=str, default="config/models.yaml",
                       help='Configuration file path')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize converter
    converter = OptimumModelConverter(args.config)
    
    # Validate dependencies
    if not converter.validate_dependencies():
        sys.exit(1)
    
    # Convert models
    if args.model == "all":
        results = converter.convert_all_models(args.format, args.output_dir)
        
        # Print summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        print(f"\nConversion Summary:")
        print(f"Successful: {successful}/{total}")
        
        for model_name, success in results.items():
            status = "✓" if success else "✗"
            print(f"  {model_name}: {status}")
        
        if successful < total:
            sys.exit(1)
            
    else:
        success = converter.convert_model(args.model, args.format, args.output_dir)
        if not success:
            sys.exit(1)
    
    print(f"Conversion completed successfully!")

if __name__ == "__main__":
    main()