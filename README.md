# RIS Generator

A desktop application that automatically generates `.ris` bibliographic files from PDF research papers using Google Gemini API.

## Features

- **Automated Metadata Extraction**: Extracts Title, Author, Year, DOI, etc., from PDF text.
- **Gemini Powered**: Uses Google Gemini 3 / 2.5 models for high-accuracy parsing.
- **Robustness**:
  - **Filename Rescue**: If text extraction fails (e.g., image-only PDF), attempts to infer metadata from the filename (adds `OCR_REQUIRED` note).
  - **Auto-Retry**: Automatically handles API rate limits and network timeouts.
- **Bulk Processing**: Scans a folder and processes all PDFs.
- **Smart Skip**: Skips text processing if a corresponding `.ris` file already exists (Configurable).

## Related Projects

- **[Zotero plugin "RIS Linker"](https://github.com/yamaizumiminoru/ris-linker)**: A plugin to bulk-import the generated `.ris` files into Zotero and automatically link the original PDFs as attachments.

## Quick Start

### Windows Users
1. Download `RisGenerator.exe` from the **[Releases](https://github.com/yamaizumiminoru/ris-generator/releases)** page.
2. Run the application.
3. Enter your [Google Gemini API Key](https://aistudio.google.com/app/apikey).
4. Select the folder containing your PDF files.
5. Click **Generate RIS Files**.

### Mac / Linux / Python Users
You can run the application directly from source:

1. **Prerequisites**: Python 3.10+
2. **Clone & Install**:
   ```bash
   git clone https://github.com/yamaizumiminoru/ris-generator.git
   cd ris-generator
   pip install -r requirements.txt
   ```
3. **Run**:
   ```bash
   python main.py
   ```
4. **Build (Optional)**:
   ```bash
   # Build a standalone executable for your OS
   pyinstaller RisGenerator.spec --clean --noconfirm
   ```

## Privacy & Security

- **No PDF Uploads**: This application does **NOT** upload your PDF files to any server. It runs locally.
- **API Processing**: Only the *text content* extracted from the PDF (and the filename) is sent to the Google Gemini API for processing.
- **No Telemetry**: No usage data is collected by the developers.
- **Local Keys**: Your API Key is stored securely in your local user profile (`AppData` or `~/.risgenerator`).

## Limitations

- **No OCR**: This app does not perform OCR on scanned PDFs.
  - If a PDF works has no text layer, it will fallback to "Filename Only" mode.
  - For best results, OCR your PDFs before using this tool.

## Troubleshooting

- **Rate Limit Exceeded (API利用制限)**:
  - The app will auto-retry. If it fails, wait a minute and try again.
- **Timeout / Deadline Exceeded (通信/混雑で時間切れ)**:
  - The API response took too long. The app will auto-retry.
- **OCR Required / Failed to read text (画像PDFのため文字読取不可)**:
  - The file has no selectable text. The app generated a basic `.ris` using only the filename. Please check the `N1` (Notes) field in Zotero.

---

## 日本語ドキュメント (Japanese Docs)

**RIS Generator** は、Google Gemini API を使用して、PDF論文から書誌情報（.risファイル）を自動生成するデスクトップアプリケーションです。

### 主な機能

- **書誌情報の自動抽出**: PDFのテキストからタイトル、著者、発行年、DOIなどを抽出します。
- **Gemini 強力パワー**: Gemini 3 / 2.5 モデルを使用し、高い精度で情報を解析します。
- **堅牢な設計**:
  - **ファイル名救済**: テキスト抽出に失敗した場合（画像PDFなど）、ファイル名からメタデータを推測して最低限の `.ris` を生成します（`OCR_REQUIRED` という注記が入ります）。
  - **自動リトライ**: API制限やタイムアウトを検知し、自動で再試行します。
- **一括処理**: フォルダを指定すると、中のPDFをまとめて処理します。
- **スキップ機能**: すでに `.ris` があるファイルは処理を飛ばします（設定で変更可能）。

### 関連プロジェクト

- **[Zotero plugin "RIS Linker"](https://github.com/yamaizumiminoru/ris-linker)**: 生成された `.ris` ファイルを一括でZoteroに取り込み、元のPDFを自動で添付ファイルとしてリンクさせるプラグインです。

### 使い方（Windows）

1. [Releases](https://github.com/yamaizumiminoru/ris-generator/releases) ページから `RisGenerator.exe` をダウンロードします。
2. アプリを起動します。
3. [Google Gemini API Key](https://aistudio.google.com/app/apikey) を入力します。
4. PDFが入っているフォルダを選択します。
5. **Generate RIS Files** ボタンを押します。

### プライバシーとセキュリティ

- **PDFはアップロードされません**: PDFファイルそのものを外部サーバーにアップロードすることはありません。
- **API処理**: 抽出された「テキストデータ」と「ファイル名」のみが、Gemini API に送信されます。
- **テレメトリなし**: 開発者が利用データを収集することはありません。
- **キーの保存**: APIキーは（保存することを選んだ場合）あなたのPC内（AppDataフォルダ等）にのみ保存されます。

### 制限事項・トラブルシューティング

- **OCR機能はありません**: スキャンされた画像PDFの場合、テキストが取れないため「ファイル名救済モード」になります。精度を上げるには、事前にOCRソフトにかけてください。
- **Rate Limit Exceeded (API利用制限)**: 自動でリトライしますが、失敗し続ける場合はしばらく待ってから実行してください。
- **Timeout (タイムアウト)**: 混雑時などに発生します。これも自動リトライされます。
