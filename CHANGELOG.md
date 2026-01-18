# Changelog

All notable changes to this project will be documented in this file.

## [v1.1.0] - 2026-01-18

### Added
- **Parallel Processing**: Significant speed improvement by processing multiple PDFs simultaneously (configurable 1-10 threads).
- **Pause/Resume**: Added ability to pause and resume the generation process.
- **Sleep Prevention**: Option to prevent Windows PC from sleeping during long batch processes.
- **UI Improvements**: Added "Parallel Processing" setting and "Resume" button to progress dialog.

## [v1.0.0] - 2026-01-16

### Added
- Initial release of RIS Generator (v1).
- Feature: Recursive PDF scanning (ignoring subfolders by default).
- Feature: Text extraction and Gemini API integration for metadata generation.
- Feature: "Filename Only" rescue mode for PDFs with no extractable text.
- Feature: Skip existing `.ris` files option.
- UI: Bilingual error messages (English/Japanese).
- UI: Model selection (Gemini 3 Flash/Pro, 2.5 Flash/Pro).
- Reliability: Automatic retry logic for API rate limits and timeouts.
