# NLP Model Conversion Toolkit

這個專案聚焦在「模型轉換」階段，提供一致的設定檔與腳本，協助將多個 Hugging Face 模型批次匯出成不同推理框架格式，並將成果上傳至 S3，同時更新模型登錄檔以供後續實驗流程使用。

## 環境安裝

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

若未安裝 [uv](https://docs.astral.sh/uv/)，請先依照官方文件安裝；`uv venv` 會在專案根目錄建立 `.venv`。若需使用 GPU，請確保已安裝對應的驅動與 CUDA 版本。

## 設定檔結構

預設的設定檔位於 `configs/experiment.yaml`，主要欄位說明如下：

- `models`：要轉換的 Hugging Face 模型與任務資訊。
- `conversion.frameworks`：要匯出的推理框架（預設提供 Transformers、ONNX Runtime、OpenVINO）。
- `conversion.precision`：輸出目標精度，例如 `fp32` 或 `int8`。
- `conversion.local_cache`：轉換後模型儲存於本地的路徑。
- `model_bucket`：上傳轉換成果的 S3 位置（`s3://bucket/prefix`）。
- `model_registry`：追蹤轉換成果位置的 YAML 檔。

可以依需求複製此檔案並調整內容。

## 執行模型轉換

在可存取網路的本地環境執行：

```bash
python scripts/run_conversion.py configs/experiment.yaml
```

流程會：

1. 使用 Hugging Face 下載原始模型或透過 `optimum-cli` 匯出成 ONNX / OpenVINO。
2. 將轉換結果存放於 `artifacts/converted_models/<model>/<framework>/<precision>`。
3. 上傳至 `model_bucket` 指定的 S3 路徑並更新 `model_registry`。

若只想在本地產生模型，可加上 `--skip-upload`。

## 自訂轉換流程

- 若需要額外的 `optimum-cli` 參數，可修改 `src/nlp_infer_bench/conversion.py` 中 `_convert_onnx`、`_convert_openvino` 的 command 組合。
- `conversion.precision` 與目錄命名僅作為組織用途；是否真的改變模型精度需依賴 `optimum-cli` 的參數或後處理流程。
- 預設會在 `configs/model_registry.yaml` 中維護每個模型與框架的本地路徑與 S3 位址，可作為之後推理或部署腳本的輸入。

## 架構概覽

- `nlp_infer_bench/conversion.py`：負責建立轉換任務、呼叫 `optimum-cli` 或下載原始模型，並更新登錄檔。
- `nlp_infer_bench/config.py`：解析設定檔與管理模型登錄。
- `nlp_infer_bench/s3_utils.py`：封裝 S3 上傳/下載工具函式。
- `scripts/run_conversion.py`：命令列入口。

## 注意事項

- 轉換 ONNX 與 OpenVINO 需安裝 `optimum-cli` 與相關套件，且部分模型可能需要額外參數調校。
- 若在不同地區使用 S3，請確認 IAM 權限與網路安全性設定。
- 依預設 `pyproject.toml` 所定義的依賴項即可完成模型下載與轉換，可視環境需求調整版本或新增套件。
