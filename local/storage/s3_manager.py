"""
S3 Model Storage Manager
"""

import boto3
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import yaml
from pathlib import Path
import hashlib

class S3ModelManager:
    def __init__(self, config_path: str = "config/s3_storage.yaml"):
        """
        Initialize S3 manager
        
        Args:
            config_path: S3 configuration file path
        """
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Initialize S3 client
        session = boto3.Session(profile_name=self.config['s3_config']['profile'])
        self.s3_client = session.client('s3', region_name=self.config['s3_config']['region'])
        self.bucket = self.config['s3_config']['bucket']
        
        # Storage paths
        self.models_path = self.config['storage_structure']['models_path']
        self.experiments_path = self.config['storage_structure']['experiments_path']
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def upload_model(self, model_name: str, framework: str, local_path: str, 
                    metadata: Optional[Dict] = None) -> str:
        """
        Upload model to S3
        
        Args:
            model_name: Model name
            framework: Framework type (pytorch/onnx/openvino)
            local_path: Local model path
            metadata: Model metadata
            
        Returns:
            str: S3 path
        """
        try:
            self.logger.info(f"Starting model upload: {model_name} ({framework})")
            
            # Build S3 path
            s3_prefix = f"{self.models_path}{model_name}/{framework}/"
            
            # Upload model files
            if os.path.isfile(local_path):
                # Single file
                filename = os.path.basename(local_path)
                s3_key = f"{s3_prefix}{filename}"
                self._upload_file(local_path, s3_key)
                uploaded_files = [s3_key]
            else:
                # Directory
                uploaded_files = self._upload_directory(local_path, s3_prefix)
            
            # Upload metadata
            if metadata:
                metadata_key = f"{s3_prefix}metadata.json"
                self._upload_metadata(metadata, metadata_key)
                uploaded_files.append(metadata_key)
            
            # Update model registry
            self._update_model_registry(model_name, framework, s3_prefix, uploaded_files)
            
            self.logger.info(f"Successfully uploaded model to: s3://{self.bucket}/{s3_prefix}")
            return f"s3://{self.bucket}/{s3_prefix}"
            
        except Exception as e:
            self.logger.error(f"Model upload failed: {str(e)}")
            raise
    
    def _upload_file(self, local_path: str, s3_key: str):
        """Upload single file"""
        self.logger.debug(f"Uploading file: {local_path} -> s3://{self.bucket}/{s3_key}")
        self.s3_client.upload_file(local_path, self.bucket, s3_key)
    
    def _upload_directory(self, local_dir: str, s3_prefix: str) -> List[str]:
        """Upload entire directory"""
        uploaded_files = []
        
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, local_dir)
                s3_key = f"{s3_prefix}{relative_path}".replace("\\", "/")  # Handle Windows paths
                
                self._upload_file(local_file_path, s3_key)
                uploaded_files.append(s3_key)
        
        return uploaded_files
    
    def _upload_metadata(self, metadata: Dict, s3_key: str):
        """Upload metadata"""
        metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=metadata_json.encode('utf-8'),
            ContentType='application/json'
        )
    
    def download_model(self, model_name: str, framework: str, local_path: str) -> bool:
        """
        Download model from S3
        
        Args:
            model_name: Model name
            framework: Framework type
            local_path: Local save path
            
        Returns:
            bool: Whether download was successful
        """
        try:
            self.logger.info(f"Starting model download: {model_name} ({framework})")
            
            # Build S3 prefix
            s3_prefix = f"{self.models_path}{model_name}/{framework}/"
            
            # List all files
            objects = self._list_objects(s3_prefix)
            
            if not objects:
                self.logger.warning(f"Model files not found: {s3_prefix}")
                return False
            
            # Create local directory
            os.makedirs(local_path, exist_ok=True)
            
            # Download all files
            for obj in objects:
                s3_key = obj['Key']
                relative_path = s3_key[len(s3_prefix):]
                local_file_path = os.path.join(local_path, relative_path)
                
                # Create subdirectory
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                
                # Download file
                self.logger.debug(f"Downloading: s3://{self.bucket}/{s3_key} -> {local_file_path}")
                self.s3_client.download_file(self.bucket, s3_key, local_file_path)
            
            self.logger.info(f"Successfully downloaded model to: {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Model download failed: {str(e)}")
            return False
    
    def _list_objects(self, prefix: str) -> List[Dict]:
        """List S3 objects"""
        objects = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            if 'Contents' in page:
                objects.extend(page['Contents'])
        
        return objects
    
    def list_available_models(self) -> Dict[str, List[str]]:
        """List all available models"""
        try:
            models = {}
            
            # List all objects under models directory
            objects = self._list_objects(self.models_path)
            
            for obj in objects:
                key = obj['Key']
                # Parse path: models/{model_name}/{framework}/...
                parts = key[len(self.models_path):].split('/')
                if len(parts) >= 2:
                    model_name = parts[0]
                    framework = parts[1]
                    
                    if model_name not in models:
                        models[model_name] = []
                    
                    if framework not in models[model_name]:
                        models[model_name].append(framework)
            
            return models
            
        except Exception as e:
            self.logger.error(f"Failed to list models: {str(e)}")
            return {}
    
    def _update_model_registry(self, model_name: str, framework: str, s3_path: str, files: List[str]):
        """Update model registry"""
        try:
            registry_key = f"{self.models_path}registry.json"
            
            # Try to download existing registry
            try:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=registry_key)
                registry = json.loads(response['Body'].read().decode('utf-8'))
            except self.s3_client.exceptions.NoSuchKey:
                registry = {}
            
            # Update registry
            if model_name not in registry:
                registry[model_name] = {}
            
            registry[model_name][framework] = {
                's3_path': s3_path,
                'files': files,
                'upload_time': datetime.now().isoformat(),
                'file_count': len(files)
            }
            
            # Upload updated registry
            registry_json = json.dumps(registry, indent=2, ensure_ascii=False)
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=registry_key,
                Body=registry_json.encode('utf-8'),
                ContentType='application/json'
            )
            
            self.logger.debug(f"Updated model registry: {model_name}/{framework}")
            
        except Exception as e:
            self.logger.warning(f"Failed to update registry: {str(e)}")
    
    def get_model_info(self, model_name: str, framework: str) -> Optional[Dict]:
        """Get model information"""
        try:
            registry_key = f"{self.models_path}registry.json"
            response = self.s3_client.get_object(Bucket=self.bucket, Key=registry_key)
            registry = json.loads(response['Body'].read().decode('utf-8'))
            
            return registry.get(model_name, {}).get(framework)
            
        except Exception as e:
            self.logger.error(f"Failed to get model information: {str(e)}")
            return None
    
    def upload_experiment_results(self, experiment_id: str, results_dir: str) -> str:
        """
        Upload experiment results
        
        Args:
            experiment_id: Experiment ID
            results_dir: Results directory
            
        Returns:
            str: S3 path
        """
        try:
            self.logger.info(f"Uploading experiment results: {experiment_id}")
            
            s3_prefix = f"{self.experiments_path}{experiment_id}/"
            uploaded_files = self._upload_directory(results_dir, s3_prefix)
            
            self.logger.info(f"Successfully uploaded experiment results to: s3://{self.bucket}/{s3_prefix}")
            return f"s3://{self.bucket}/{s3_prefix}"
            
        except Exception as e:
            self.logger.error(f"Failed to upload experiment results: {str(e)}")
            raise
    
    def download_experiment_results(self, experiment_id: str, local_path: str) -> bool:
        """Download experiment results"""
        try:
            s3_prefix = f"{self.experiments_path}{experiment_id}/"
            
            # List all files
            objects = self._list_objects(s3_prefix)
            
            if not objects:
                self.logger.warning(f"Experiment results not found: {experiment_id}")
                return False
            
            # Create local directory
            os.makedirs(local_path, exist_ok=True)
            
            # Download all files
            for obj in objects:
                s3_key = obj['Key']
                relative_path = s3_key[len(s3_prefix):]
                local_file_path = os.path.join(local_path, relative_path)
                
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                self.s3_client.download_file(self.bucket, s3_key, local_file_path)
            
            self.logger.info(f"Successfully downloaded experiment results to: {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download experiment results: {str(e)}")
            return False

def main():
    """Test S3 manager"""
    logging.basicConfig(level=logging.INFO)
    
    manager = S3ModelManager()
    
    # Test listing available models
    models = manager.list_available_models()
    print(f"Available models: {models}")

if __name__ == "__main__":
    main()