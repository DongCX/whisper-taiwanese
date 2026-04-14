# ROADMAP

這份文件只記錄「已討論但尚未實作」的方向，供後續 thread 接手評估、切 task、決定優先順序。

## 已確認的前提

- 這個 repo 的責任是「吃本機影音檔，輸出逐字稿與字幕」。
- 影片下載會拆到另一個專案處理，不放在這個 repo。
- 目前實測下來，`tw-mandarin`（`MediaTek-Research/Breeze-ASR-25`）是較好的預設方向。

## P1: 直接影響辨識品質

### 1. VAD 分段後再做 ASR

目的：
- 先把有講話的區段切出來，再逐段送進 ASR。
- 降低長音訊、停頓、背景音樂、靜音段對辨識的干擾。

討論重點：
- 是否採用 `silero-vad`、`pyannote`，或其他較輕量方案。
- 要輸出原始 VAD segment，還是只當內部前處理。
- 需要如何和現有時間戳、字幕切句整合。

### 2. `initial prompt` / `hotwords` / glossary

目的：
- 提高人名、地名、政黨名、節目固定詞、台語常錯詞的命中率。

討論重點：
- CLI 介面要用 `--initial-prompt`、`--hotwords`、`--glossary-file`，還是三者並存。
- glossary 要只做 decode prompt，還是再加一層保守 replacement。
- 怎麼避免 prompt 過強導致 hallucination。

### 3. 音訊前處理

目的：
- 在進 ASR 前做降噪、人聲增強、音量正規化、背景音樂抑制。

討論重點：
- 只靠 `ffmpeg` filter 還是接更完整的 denoise / separation pipeline。
- 是否做成可選旗標，例如 `--normalize-audio`、`--denoise`、`--voice-enhance`。
- 要不要保留前處理後的中間音檔供人工比對。

### 4. Benchmark / compare workflow

目的：
- 用固定測試片段比較不同模型、不同 prompt、不同前處理參數。

討論重點：
- 是否新增一個 `benchmark` 或 `compare` 指令。
- benchmark 資料格式要怎麼定義，例如 `audio + reference transcript + metadata`。
- 指標要看 WER / CER / 關鍵詞命中率，還是先用人工 review 輔助。

## P2: 提升字幕與輸出品質

### 5. 更好的字幕切句規則

目前狀態：
- 現在主要根據字數、秒數、停頓、句尾標點切字幕。

可改善方向：
- 依標點、語氣停頓、閱讀速度、兩行平衡重新切句。
- 避免把固定詞組、專有名詞、短語硬拆開。
- 針對台語 / 華語混講調整切句策略。

### 6. 保守型 LLM 後處理

目的：
- 在不任意改寫內容的前提下，修正常見錯字、補標點、統一專有名詞寫法。

討論重點：
- 必須限制成「保守校正」，不能變成摘要或重寫。
- 需不需要提供 `raw transcript` 與 `normalized transcript` 兩份輸出。
- glossary 規則和 LLM 校正的優先順序如何安排。

## P3: 進階能力

### 7. 講者分離 / speaker diarization

目的：
- 區分不同講者，輸出 `Speaker 1` / `Speaker 2` 之類的標記。

討論重點：
- 這是獨立於 ASR 的另一條 pipeline，不是單靠現有 Whisper 輸出就能穩定做到。
- 要輸出 speaker-tagged JSON，還是連 SRT / VTT 都帶講者標記。
- 重疊說話、背景音樂、現場噪音對效果的影響需要先做風險評估。

### 8. 依內容自動路由模型

目的：
- 讓工具依素材特性在 `tw-mandarin`、`balanced`、`nutn-v0.5` 間自動挑選或重跑。

討論重點：
- 是否先跑一版 baseline，再依結果判斷是否需要重試其他模型。
- 如何定義「台語比例高」或「結果低信心」的條件。
- 自動重跑會增加多少延遲與成本。

### 9. ASR fine-tune 研究

目的：
- 如果通用模型對固定領域素材仍不夠準，評估針對該 domain 做 ASR 微調。

前提：
- 需要成對的 `音訊 + 高品質逐字稿`，不是只拿文字資料或一般 LLM instruction data。

討論重點：
- 要 fine-tune 哪個 ASR 基底模型。
- 需要多少小時標註資料才值得做。
- 是先做 glossary / prompt / VAD，還是真的已經碰到 base model 上限。

## 建議的討論順序

1. 先做 `VAD 分段`。
2. 再做 `hotwords / glossary / initial prompt`。
3. 補 `benchmark / compare`，讓後續調參有客觀基準。
4. 再評估 `音訊前處理` 與 `保守型 LLM 後處理`。
5. 最後才進到 `speaker diarization` 或 `ASR fine-tune`。
