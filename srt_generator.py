import whisper
from whisper.utils import get_writer
import os
import argparse
import sys
from contextlib import contextmanager

class Tee:
    """Helper class to write to multiple streams (e.g., stdout and a file)."""
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

@contextmanager
def redirect_to_log(log_file_path):
    """Redirects stdout to both the console and the specified log file."""
    if not log_file_path:
        yield
        return
    
    with open(log_file_path, "w", encoding="utf-8") as f:
        original_stdout = sys.stdout
        sys.stdout = Tee(original_stdout, f)
        try:
            yield
        finally:
            sys.stdout = original_stdout

def generate_srt(video_path, language="it", model_size="medium", log_enabled=False):
    if not os.path.exists(video_path):
        print(f"Error: File not found at {video_path}")
        return

    # Prepare the output directory and base name
    output_dir = os.path.dirname(os.path.abspath(video_path))
    video_filename = os.path.basename(video_path)
    file_base = os.path.splitext(video_filename)[0]
    
    log_file_path = None
    if log_enabled:
        # The log filename is always log_{video_name}.txt
        log_file_path = os.path.join(output_dir, f"log_{file_base}.txt")
        print(f"Logging enabled. Log file: {log_file_path}")

    with redirect_to_log(log_file_path):
        print(f"Loading Whisper model ({model_size})...")
        model = whisper.load_model(model_size)

        print(f"Starting transcription for: {video_filename} [Language: {language if language else 'auto-detect'}]")
        
        # Transcribe the video. verbose=True prints segments to stdout.
        # This output will now be captured by the Tee class if log_enabled is True.
        result = model.transcribe(video_path, language=language, verbose=True)

        # Prepare the writer
        writer = get_writer("srt", output_dir)

        # The writer expects the result and the original file path to derive the output name
        writer(result, video_path)

        # Construct the expected srt path for the success message
        srt_path = os.path.join(output_dir, f"{file_base}.srt")
        print(f"\n✅ Done! Subtitles saved to: {srt_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate SRT subtitles from an MP4 file using OpenAI Whisper.")
    parser.add_argument("input_file", help="Path to the input MP4 file")
    parser.add_argument("-l", "--language", default="it", help="Transcription language code (e.g., 'it', 'en', 'auto'). Default: it")
    parser.add_argument("-m", "--model", default="medium", help="Whisper model size (tiny, base, small, medium, large). Default: medium")
    parser.add_argument("--log", choices=['y', 'n'], default='n', help="Enable logging (y/n). Default: n")
    parser.add_argument("--log_file", help="Path for the log (Note: filename will be automatically set to log_{video_name}.txt in the input folder)")

    args = parser.parse_args()

    # Normalize language: if 'auto', pass None to whisper to trigger auto-detection
    lang = None if args.language.lower() == "auto" else args.language
    
    # Enable logging if --log is 'y'
    log_enabled = args.log.lower() == 'y'

    generate_srt(args.input_file, lang, args.model, log_enabled)
