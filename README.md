# SRT Generator

This tool automatically generates `.srt` subtitle files from `.mp4` videos using OpenAI's Whisper model.

## Features
- Transcribes audio from MP4 files.
- Automatically saves the `.srt` file in the same directory as the video.
- Supports multiple languages; auto-detects by default, or pin one with `--language`.
- Choice of Whisper models (`tiny`/`base`/`small`/`medium`/`large*`/`turbo`, plus the
  English-only `.en` variants) for different speed/accuracy trade-offs. The list is
  read from the installed whisper build, so `--help` always shows what you can run.
- **Progress reporting**: prints the position reached as `mm:ss / mm:ss` with a
  percentage, speed multiplier and ETA.
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
   git clone https://github.com/madsomma/mp4-to-srt.git
   cd mp4-to-srt
   ```

2. **Create a virtual environment**:
   It is recommended to use a virtual environment to manage dependencies. Create one in the `.venv` subfolder:
   ```bash
   python3 -m venv .venv
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
   pip3 install -r requirements.txt
   ```

> **Note**: The `.venv` directory file is excluded from the repository. You must create the virtual environment locally following the steps above.

## Usage

To ensure you are using the correct dependencies, run the script using the Python interpreter from the virtual environment created in the installation steps.

### Basic Usage
By default, the script **auto-detects** the language and uses the **large** model:

**macOS / Linux:**
```bash
./.venv/bin/python srt_generator.py path/to/your_video.mp4
```

**Windows:**
```bash
.\.venv\Scripts\python srt_generator.py path/to/your_video.mp4
```

### Specify Language
Pinning the language is faster and more reliable than detection when you know it:

```bash
./.venv/bin/python srt_generator.py video.mp4 --language en
```

### Change Model Size
Use a different model for better accuracy or faster processing:
- `tiny` / `base`: Very fast, lower accuracy.
- `medium`: Good balance of speed and accuracy.
- `large`: Most accurate, needs the most memory and time (**default**).
- `turbo` / `large-v3-turbo`: Near-`large` accuracy at a fraction of the runtime.

Run `srt_generator.py --help` for the full list supported by your install.

```bash
./.venv/bin/python srt_generator.py video.mp4 --model turbo
```

### Progress
Every 10 seconds the script prints how far into the audio it has got:

```
[progress] 10:04 / 43:56 ( 22.9%)  3.1x  eta 10:52
```

That reads as: 10:04 of a 43:56 file done, running at 3.1x realtime, about 10:52
left. Change the cadence with `--progress-interval 30`, or pass
`--progress-interval 0` to fall back to whisper's own frame-based bar.

> **Note**: whisper skips silent windows without reporting them, so on media with
> long silences the position can jump forward in large steps.

### Logging
To enable logging of the transcription process to a file, use the `--log y` flag. You can also provide a path for the log with `--log_file`. The log file will be automatically named `log_{video_name}.txt` and saved in the same directory as the input video.

```bash
./.venv/bin/python srt_generator.py video.mp4 --log y --log_file .
```

## Options Summary

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `input_file` | - | Path to the MP4 file | (Required) |
| `--language` | `-l` | ISO language code (it, en, fr...) or `auto` | `auto` |
| `--model` | `-m` | Whisper model size | `large` |
| `--progress-interval` | - | Seconds between progress lines (0 = off) | `10` |
| `--log` | - | Enable logging (y/n) | `n` |
| `--log_file` | - | Path for the log file | - |
