# Tech in Cheese - SRT Generator

This tool automatically generates `.srt` subtitle files from `.mp4` videos using OpenAI's Whisper model.

## Features
- Transcribes audio from MP4 files.
- Automatically saves the `.srt` file in the same directory as the video.
- Supports multiple languages (defaults to Italian).
- Choice of Whisper models (tiny, base, small, medium, large) for different speed/accuracy trade-offs.
- **Logging support**: Capture transcription output into a `.txt` file.

## Prerequisites

1. **Python 3.8+**
2. **FFmpeg**: Whisper requires FFmpeg to process media files.
   - **macOS (Homebrew):**
     ```bash
     brew install ffmpeg
     ```
   - **Windows (Chocolatey):**
     ```bash
     choco install ffmpeg
     ```
   - **Linux (apt):**
     ```bash
     sudo apt update && sudo apt install ffmpeg
     ```

## Installation

Follow these steps to set up the project locally:

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd mp4-to-srt
   ```

2. **Create a virtual environment**:
   It is recommended to use a virtual environment to manage dependencies. Create one in the `.venv` subfolder:
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**:
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```
   - **Windows**:
     ```bash
     .venv\Scripts\activate
     ```

4. **Install the required Python packages**:
   Once the virtual environment is active, install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

> **Note**: The `.venv` directory and `GEMINI.md` file are excluded from the repository. You must create the virtual environment locally following the steps above.

## Usage

Ensure your virtual environment is activated before running the script.

### Basic Usage (Italian)
By default, the script transcribes in **Italian** using the **medium** model:

```bash
python srt_generator.py path/to/your_video.mp4
```

### Specify Language
To transcribe in a different language (e.g., English):

```bash
python srt_generator.py video.mp4 --language en
```

### Auto-detect Language
If you're not sure about the language:

```bash
python srt_generator.py video.mp4 --language auto
```

### Change Model Size
Use a different model for better accuracy or faster processing:
- `tiny` / `base`: Very fast, lower accuracy.
- `medium`: Good balance (Default).
- `large`: Most accurate, requires more memory/time.

```bash
python srt_generator.py video.mp4 --model large
```

### Logging
To enable logging of the transcription process to a file, use the `--log y` flag. You can also provide a path for the log with `--log_file`. The log file will be automatically named `log_{video_name}.txt` and saved in the same directory as the input video.

```bash
python srt_generator.py video.mp4 --log y --log_file .
```

## Options Summary

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `input_file` | - | Path to the MP4 file | (Required) |
| `--language` | `-l` | ISO language code (it, en, fr, auto) | `it` |
| `--model` | `-m` | Whisper model size | `medium` |
| `--log` | - | Enable logging (y/n) | `n` |
| `--log_file` | - | Path for the log file | - |
