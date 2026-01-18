# 日本語版（公開用：RISジェネレーター＋RIS Linker 完全ガイド）

## 0) 文献管理ソフトがない状態だと、何がつらい？

文系の研究って、文献のPDFが増えるほど、だんだん面倒になってくる。

- PDFがPCのあちこちに散らばる（Downloads、デスクトップ、外付け、クラウド…）
- 「あの論文どこだっけ？」が日常化して、検索しても見つからない
- 見つけても、**引用に必要な情報（著者・年・タイトル・媒体名・ページ）を毎回PDFから拾い直す**
- 参考文献リストは手作業になり、フォーマット直しで時間が溶ける
- 共同研究やPC移行で一気に崩壊する（ファイルはあるのに、意味のある整理がない）

この状態の本質は、**PDFはあるのに「目録（書誌情報）」がない**こと。 つまり「本棚はあるけど、カード目録がない図書館」みたいなもの。

## 0.5) ソリューション：文献管理ソフト（例：Zotero）

ここを解決する道具が、文献管理ソフト。代表例がZotero。 やりたいことはシンプルで、PDFを「ただのファイル」から「書誌情報つきの文献」に昇格させること。

ただし問題はひとつ。**“昇格”のための入力が大変すぎる**。

## 1) Zoteroに文献を登録すると、何ができるようになる？

Zoteroは、ざっくり言うと「論文・本・章・報告書の“台帳”＋PDF保管庫」です。文献がZoteroに入ると、次のことが一気に楽になります。

- **引用が一発**：Word/LibreOffice/Google Docs等で、引用（著者年・脚注）と参考文献リストを自動生成
- **整理が爆速**：コレクション、タグ、検索、重複整理、メモ、関連文献リンク
- **再発見できる**：数年後に「このテーマのやつどこ？」が検索で出てくる
- **PDFとメタデータが結びつく**：タイトル・著者・年・媒体名などが付いた“文献”として扱える
- **研究の資産化**：引っ越し・PC買い替え・共同研究でも崩れにくい

## 2) じゃあ、なぜ文系研究者はそれができなかったの？

結論はシンプルで、**PDFに“機械が読める書誌情報”が入ってないことが多い**から。

文系あるあるを挙げると：

- **DOIがない**（特に日本語の論文・紀要・章・報告書）
- **スキャンPDF**（画像だけで文字が取れない＝メタデータ抽出ができない）
- **本・章・会議録はメタデータが複雑**（雑誌論文みたいに単純じゃない）
- **PDFが手元にあるだけ**で、出版社サイトやDBコネクタで拾えない

そして、ここが本題：

> 結果として、Zoteroに入れるには **手入力（＝時間が溶ける）** になりがち。

これが非現実的なのは、単に「量が多い」からじゃない。 手入力は、やればやるほど次の3つで詰みやすい。

- **終わらない**：新しいPDFは増え続けるのに、入力は後回しになり、未整理が積み上がる
- **崩れる**：誤字・表記ゆれ・媒体名の揺れ・章の扱いなどが蓄積して、後で検索・引用時に効いてくる
- **研究が止まる**：引用や参考文献リスト作成のたびに「どれが正しい情報か」をPDFから掘り返す作業が戻ってくる

つまり手入力は「頑張ればできる作業」ではなく、**研究時間を吸い続ける構造**になりがち。

## 3) そこでこの2つ：今回のソリューション

今回の仕組みは役割分担が明確で、PDFをZoteroに流し込むための最短ルートです。

### A. RISジェネレーター（PDF → RIS を作る）

- PDFフォルダを一括処理して、`foo.pdf` に対し `foo.ris` を生成
- DOIがなくても、**本文テキスト**や（場合によっては）**ファイル名**から書誌情報を推定
- 生成されたRISは、Zotero等が読める“文献カード”になる

リポジトリ： [https://github.com/yamaizumiminoru/ris-generator](https://github.com/yamaizumiminoru/ris-generator)

### B. RISインポートプラグイン（RIS Linker：RISを一括導入してPDFを自動添付）

- フォルダ内の `.ris` を一括インポート
- `foo.ris` と同じ場所に `foo.pdf` があれば、自動でPDF添付
- 大量でも固まりにくく、キャンセルでき、結果サマリーとレポートを残す

リポジトリ： [https://github.com/yamaizumiminoru/zotero-ris-linker](https://github.com/yamaizumiminoru/zotero-ris-linker)

この2つをつなぐと、こうなる：

**PDFフォルダ →（RISジェネレーター）→ RIS生成 →（RIS Linker）→ Zoteroに文献＋PDFが一括登録**

## 4) 使い方（超初心者向け・最短ルート）

### 事前準備：PDFは1つのフォルダにまとめる（サブフォルダは対象外）

- PDFはできるだけ**1つのフォルダにまとめる**（サブフォルダは対象外の仕様にしている場合が多い）
- 可能ならファイル名を整える（救済率が上がる）：
  - 例）`2020_Suzuki_Title.pdf` のように「年・著者・タイトル」が入ると強い
- `.ris` と `.pdf` は **basename一致**が鍵
  - `foo.ris` と `foo.pdf` が同じフォルダにある状態が理想

---

### Step 1：Gemini APIキーを取得する（RISジェネレーター用）

RISジェネレーターはLLM APIを使うので、APIキーが必要です。 キー作成はGoogle AI Studioから行えます。

Google AI Studio（APIキー作成ページの例）： [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

**手順（ざっくり）**

- Google AI Studio（Gemini API）にログイン
- 「Get API key」→「Create API key」
- 生成されたキーをコピー（他人に見せない／GitHubに上げない）

※キーはパスワード同等。漏れたら作り直し推奨。

---

### Step 2：RISジェネレーターで `.ris` を作る

- `RisGenerator.exe` を起動
- PDFフォルダを選ぶ
- APIキーを貼る（保存するかは好み。共用PCなら保存しない）
- 実行 → 完了画面で結果を見る
  - Success（本文から生成）
  - Success（Filename Only：本文が取れない場合でもファイル名から救済）
  - OCR required（画像だけPDF）
  - Failed（通信やタイムアウトなど）

**よくある注意**

- 画像だけPDFはOCRが必要（まずは外部OCR→再実行が早い）
- タイムアウト/混雑系エラーは「そのファイルだけ再実行」で通ることが多い
- 自由記述フィールド（タイトル・著者など）には、不確実性が `? / ?? / ???` で付く場合がある（後で見直しやすくするため）

---

### Step 3：ZoteroにRIS Linker（.xpi）を入れる

Zotero 7ではプラグイン導入は **Tools → Plugins** から行います。

**インストール**

- Zotero（バージョン7系）をインストール
- GitHub Releasesから `.xpi` をダウンロード
  - プラグインのリポジトリ： [https://github.com/yamaizumiminoru/zotero-ris-linker](https://github.com/yamaizumiminoru/zotero-ris-linker)
- Zotero → Tools → Plugins
- 歯車 → Install Plugin from File… で `.xpi` を選ぶ （またはPlugins画面にドラッグ＆ドロップでも可）
- 必要ならZotero再起動

---

### Step 4：RIS Linkerで一括インポート＋PDF自動添付

- RISとPDFが同じフォルダにある状態にする（`foo.ris` と `foo.pdf`）
- RIS Linkerを起動（メニューから）
- 対象フォルダを選択して実行
- 終了後、サマリー（Imported / Skipped / Failed / Linked…）とレポートを確認

## 5) よくある詰まりポイント（ここだけ読めば助かる）

- **OCR requiredが多い**：PDFをOCRしてから再実行
- **Failedが少数出る**：通信・混雑が多いので、失敗分だけ再実行で通ることが多い
- **Zoteroに入れた後の微修正**：`?` が付いた自由記述フィールド（タイトル/著者など）は、参考文献として挙げる際に確認

---

# English version (public-ready: RIS Generator + RIS Linker full guide)

## 0) What’s painful when you have no reference manager?

In humanities research, as the number of PDFs grows, your work gradually shifts from “research” to “search and re-search.”

- PDFs get scattered across Downloads, Desktop, external drives, and cloud folders
- “Where was that paper again?” becomes a daily question—and you still can’t find it
- Even when you do, you repeatedly re-extract citation details from the PDF: author, year, title, venue, pages
- Bibliographies become manual work, and formatting fixes eat time
- Collaboration or switching computers can make the whole system collapse (files exist, but meaningful organization doesn’t)

At the core: you have PDFs, but you don’t have a **catalog** (reliable bibliographic metadata). It’s like having shelves of books without catalog cards.

## 0.5) The solution: a reference manager (e.g., Zotero)

This is exactly what reference managers are for. Zotero is a well-known example. The goal is simple: promote a PDF from “just a file” to “a proper reference item with metadata.”

But there’s one big problem: **the “promotion step” is painfully expensive**.

## 1) What becomes possible once references are registered in Zotero?

Zotero is essentially a **bibliography ledger + PDF archive** for papers, books, chapters, and reports. Once your sources are in Zotero, many tasks become dramatically easier:

- **One-click citations**: generate in-text citations (author–year or footnotes) and bibliographies in Word / LibreOffice / Google Docs
- **Fast organization**: collections, tags, search, duplicate handling, notes, related-item links
- **Reliable rediscovery**: years later, “Where was that source?” becomes a quick search
- **PDF + metadata stay linked**: title/author/year/venue are tied to the PDF as a single reference item
- **A durable research asset**: your library survives moves, new PCs, and collaboration far better than ad-hoc folders

## 2) Why was this especially hard for humanities researchers?

The short answer: **many PDFs do not contain machine-readable bibliographic metadata**.

Common humanities pain points:

- **No DOI** (especially for local journals, bulletins, chapters, and reports)
- **Scanned PDFs** (image-only → no extractable text → metadata can’t be extracted)
- **Books/chapters/proceedings have complex metadata** (not as simple as standard journal articles)
- **You only have the PDF locally**, so publisher sites or database/browser connectors can’t “pick it up”

And this is the key consequence:

> As a result, you often end up doing **manual entry**—which means your time simply evaporates.

This becomes unrealistic not just because of the volume, but because manual entry tends to fail in three predictable ways:

- **It never finishes**: new PDFs keep coming, entry gets postponed, and the “to-be-entered” pile grows
- **Quality drifts**: typos, name variants, inconsistent venue names, and edge cases (chapters/reports/bulletins) accumulate—and later break search and citation workflows
- **Research slows down**: whenever you cite or build a bibliography, you end up digging into the PDF again to confirm what’s correct

So manual entry isn’t simply “hard but doable.” It often turns into a **structural time sink** that keeps stealing research time.

## 3) The two tools: the solution

This workflow splits responsibilities cleanly and provides a short, practical path from a PDF folder to a usable Zotero library.

### A. RIS Generator (PDF → RIS)

- Batch-process a PDF folder and generate `foo.ris` for each `foo.pdf`
- Even without a DOI, it infers bibliographic metadata from **document text**, and sometimes from the **filename**
- The generated RIS acts like a “reference card” that Zotero can import

Repository: [https://github.com/yamaizumiminoru/ris-generator](https://github.com/yamaizumiminoru/ris-generator)

### B. RIS Import Plugin (RIS Linker: bulk import RIS + auto-attach PDFs)

- Bulk-import `.ris` files from a folder
- If `foo.pdf` exists next to `foo.ris`, the PDF is attached automatically
- Designed for large batches: less freezing, cancellable runs, clear summary + report

Repository: [https://github.com/yamaizumiminoru/zotero-ris-linker](https://github.com/yamaizumiminoru/zotero-ris-linker)

Together, the workflow becomes:

**PDF folder → (RIS Generator) → RIS files → (RIS Linker) → Zotero items + PDFs attached**

## 4) How to use (beginner-friendly, shortest route)

### Preparation: put PDFs in one folder (subfolders are not included)

- Put PDFs into **one folder** (subfolders are typically not included by design)
- If possible, clean up filenames (this improves rescue mode):
  - Example: `2020_Suzuki_Title.pdf` (year/author/title helps a lot)
- Basename matching matters:
  - Having `foo.ris` and `foo.pdf` in the same folder is the ideal setup

---

### Step 1: Get a Gemini API key (for RIS Generator)

RIS Generator uses an LLM API, so you need an API key. You can create a key via Google AI Studio.

Google AI Studio (example API key page): [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

Quick steps:

- Log in to Google AI Studio (Gemini API)
- Click “Get API key” → “Create API key”
- Copy the key (do not share it / do not upload it to GitHub)

Treat the key like a password. If it leaks, rotate it.

---

### Step 2: Generate `.ris` files with RIS Generator

- Launch `RisGenerator.exe`
- Select your PDF folder
- Paste your API key (saving it is optional; avoid saving on shared PCs)
- Run → check the final results:
  - Success (generated from text)
  - Success (Filename Only: rescued from filename when text is unavailable)
  - OCR required (image-only PDFs)
  - Failed (network/timeout, etc.)

Common notes:

- Image-only PDFs often need OCR first (external OCR → re-run is usually fastest)
- Timeouts / congestion errors often go away if you re-run only the failed files
- Free-text fields (title/author, etc.) may include `? / ?? / ???` to make uncertain values easy to review later

---

### Step 3: Install RIS Linker (`.xpi`) in Zotero

In Zotero 7, plugins are installed via **Tools → Plugins**.

Install:

- Install Zotero (version 7.x)
- Download the `.xpi` from GitHub Releases
  - Plugin repository: [https://github.com/yamaizumiminoru/zotero-ris-linker](https://github.com/yamaizumiminoru/zotero-ris-linker)
- Zotero → Tools → Plugins
- Gear icon → “Install Plugin from File…” and select the `.xpi` (Drag & drop into the Plugins window may also work)
- Restart Zotero if needed

---

### Step 4: Bulk import + auto-attach with RIS Linker

- Make sure `foo.ris` and `foo.pdf` are in the same folder
- Launch RIS Linker (from the menu)
- Select the target folder and run
- After completion, review the summary (Imported / Skipped / Failed / Linked…) and the report

## 5) Common sticking points (read this first if you’re stuck)

- **Many “OCR required”**: OCR the PDFs, then re-run
- **A few “Failed”**: often network/congestion—re-running only failed files usually works
- **Post-import cleanup**: for free-text fields marked with `?` (title/author, etc.), verify them before using the item in a bibliography

---

<br>
