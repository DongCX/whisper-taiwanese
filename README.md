# whisper-taiwanese

`whisper-taiwanese` 是一個本機 CLI，給定影片或音訊檔後，會：

- 抽出 16kHz mono WAV
- 以 Whisper 相容的台語 ASR 模型產生逐字稿
- 輸出 `.txt`、`.json`、`.srt`、`.vtt`

目前支援單檔與整個資料夾的批次處理，預設 preset 是 `tw-mandarin`（`MediaTek-Research/Breeze-ASR-25`）。

## Requirements

- `ffmpeg`
- `uv`
- Python `3.11` 到 `3.13`

這個 repo 目前用 `.python-version = 3.12`，避免直接踩到 `torch` 對 `Python 3.14` 的相容性問題。

## Install

```bash
uv sync --python 3.12
```

第一次執行會從 Hugging Face 下載模型，所以需要網路。模型檔案不小（`tw-mandarin` 與 `balanced` 約數 GB），請預留足夠磁碟空間與下載時間。快取預設放在 `~/.cache/huggingface/hub/`。

## Usage

最簡單的單檔用法：

```bash
uv run taiwanese-transcribe /path/to/video.mp4
```

這會直接使用 `MediaTek-Research/Breeze-ASR-25`。

輸出會預設寫到 `outputs/`：

- `outputs/<stem>.txt`
- `outputs/<stem>.json`
- `outputs/<stem>.srt`
- `outputs/<stem>.vtt`

指定輸出目錄與檔名：

```bash
uv run taiwanese-transcribe /path/to/video.mp4 \
  --output-dir outputs/interview \
  --output-stem ep01
```

切換模型：

```bash
uv run taiwanese-transcribe /path/to/video.mp4 --preset balanced
uv run taiwanese-transcribe /path/to/video.mp4 --preset nutn-v0.5
uv run taiwanese-transcribe /path/to/video.mp4 --preset tw-mandarin
uv run taiwanese-transcribe /path/to/video.mp4 --model NUTN-KWS/Whisper-Taiwanese-model-v0.5
```

批次處理整個資料夾：

```bash
uv run taiwanese-transcribe /path/to/media-folder --output-dir outputs/batch
```

資料夾模式會：

- 遞迴搜尋常見影音副檔名
- 在 `outputs/batch/` 下保留原本的相對目錄結構
- 每個媒體檔各自產出 `.txt`、`.json`、`.srt`、`.vtt`
- 如果同一層有同名不同副檔名，例如 `clip.mp4` 和 `clip.wav`，會自動避開輸出檔名衝突

## Makefile flow

安裝依賴：

```bash
make sync
```

跑測試：

```bash
make test
```

轉單一影片：

```bash
make transcribe INPUT=/path/to/video.mp4
```

批次轉整個資料夾：

```bash
make batch INPUT=/path/to/media-folder OUT=outputs/batch
```

指定輸出目錄、檔名與額外旗標：

```bash
make transcribe \
  INPUT=/path/to/video.mp4 \
  OUT=outputs/interview \
  STEM=ep01 \
  FLAGS="--keep-wav --overwrite"
```

批次模式不支援 `STEM`，因為每個輸入檔都會保留自己的檔名。

如果想切到較小模型：

```bash
make transcribe INPUT=/path/to/video.mp4 PRESET=balanced
make transcribe INPUT=/path/to/video.mp4 PRESET=tw-mandarin
```

查看可用目標：

```bash
make help
```

## Model presets

- `nutn-v0.5`: `NUTN-KWS/Whisper-Taiwanese-model-v0.5`
  - CC BY-NC 4.0
  - 適合偏台語內容
  - 模型卡明示訓練資料偏中小學教材與學生學習資料
- `balanced`: `openai/whisper-large-v3-turbo`
  - MIT
  - 泛用性較強，適合對談、夾華語、夾英文的 baseline
- `tw-mandarin`: `MediaTek-Research/Breeze-ASR-25`
  - 預設值
  - Apache-2.0
  - 模型卡明示強化台灣華語與中英混用，並強化時間戳記對齊

三個 preset 都可以被 `--model` 覆蓋，所以之後你要換成本地模型路徑或其他 Hugging Face 模型，不需要改程式。

## Notes

- `--device auto` 會依序嘗試 `CUDA`、`MPS`、`CPU`
- `--keep-wav` 會把抽出的 `wav` 一起保留到輸出目錄
- `--overwrite` 允許覆寫既有輸出
- `--language zh` 是目前預設；如果是台語、華語混講或結果明顯怪，可以試 `--language auto`
- `--chunk-length 0` 代表不要對 Whisper 額外切塊，這是目前預設，也是較建議的設定
- 如果你遇到記憶體壓力，再考慮用 `--chunk-length 25` 這種值切回 pipeline chunking，但辨識品質可能下降
- 長音訊推論目前會開啟 Whisper 官方文件建議的 repetition / low-confidence fallback 參數，降低重複亂字
- `--max-chars` 和 `--max-seconds` 可以調整字幕切分

查看完整參數：

```bash
uv run taiwanese-transcribe --help
```

## License

本專案原始碼以 MIT License 釋出，詳見 [`LICENSE`](LICENSE)。

注意：本專案本身不包含任何模型權重，執行時會從 Hugging Face 下載第三方模型，各自有獨立授權：

- `MediaTek-Research/Breeze-ASR-25`：Apache-2.0
- `openai/whisper-large-v3-turbo`：MIT
- `NUTN-KWS/Whisper-Taiwanese-model-v0.5`：CC BY-NC 4.0（**非商用**）

商用情境請避開 `nutn-v0.5` preset，或改用其他授權相容的模型。
