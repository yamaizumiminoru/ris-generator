# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| v0.x    | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please create a GitHub Issue or contact the repository owner directly.

## Privacy Statement

- **No Telemetry**: This application does not collect usage data or send telemetry to the developers.
- **API Usage**:
  - The application sends extracted text from your PDFs to the Google Gemini API for processing.
  - Your API Key is stored locally on your device (if you choose to save it) in your OS's application data folder.
  - The application does NOT upload your PDF files to any third-party server other than the text content sent to the configured LLM API.
