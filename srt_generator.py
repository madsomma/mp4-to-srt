"""Generate SRT subtitles from a media file using OpenAI Whisper."""

from __future__ import annotations

import argparse
import functools
import importlib
import os
import shutil
import sys
import time
from contextlib import contextmanager
from types import SimpleNamespace
from typing import IO, Generator, Optional, Sequence

import whisper
from whisper.audio import HOP_LENGTH, SAMPLE_RATE
from whisper.utils import get_writer

# Sourced from the installed whisper build so the choices never drift from it
# (adds the English-only *.en variants and large-v3-turbo on current releases).
MODEL_SIZES: tuple[str, ...] = tuple(whisper.available_models())

DEFAULT_MODEL = "large"
DEFAULT_LANGUAGE = "auto"
DEFAULT_PROGRESS_INTERVAL = 10.0

# whisper works on mel-spectrogram frames; this converts one frame to seconds
# of audio (160 / 16000 = 10 ms), which is what makes a frame count printable
# as a timestamp.
FRAME_SECONDS = HOP_LENGTH / SAMPLE_RATE

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_DEPENDENCY_ERROR = 2
EXIT_RUNTIME_ERROR = 3


class Tee:
    """Write to multiple text streams at once (e.g. stdout and a log file)."""

    def __init__(self, *files: IO[str]) -> None:
        if not files:
            raise ValueError("Tee requires at least one stream")
        self.files = files

    def write(self, data: str) -> int:
        for f in self.files:
            f.write(data)
            f.flush()
        return len(data)

    def writelines(self, lines: Sequence[str]) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        for f in self.files:
            f.flush()

    # Delegate the stream introspection APIs libraries probe on sys.stdout.
    def isatty(self) -> bool:
        return getattr(self.files[0], "isatty", lambda: False)()

    def fileno(self) -> int:
        return self.files[0].fileno()

    @property
    def encoding(self) -> str:
        return getattr(self.files[0], "encoding", "utf-8")


@contextmanager
def redirect_to_log(log_file_path: Optional[str]) -> Generator[None, None, None]:
    """Mirror stdout and stderr into ``log_file_path`` for the duration of the block.

    stderr is included because whisper's tqdm progress bar writes there; without
    it the log would miss the transcription progress the README promises.
    """
    if not log_file_path:
        yield
        return

    with open(log_file_path, "w", encoding="utf-8") as f:
        original_stdout, original_stderr = sys.stdout, sys.stderr
        sys.stdout = Tee(original_stdout, f)
        sys.stderr = Tee(original_stderr, f)
        try:
            yield
        finally:
            sys.stdout, sys.stderr = original_stdout, original_stderr


def format_timestamp(seconds: float) -> str:
    """Render ``seconds`` as M:SS, or H:MM:SS once past the hour."""
    total = int(max(seconds, 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class AudioProgress:
    """Stand-in for ``tqdm.tqdm`` that reports audio position, not frame counts.

    whisper's ``transcribe()`` only touches the constructor, the context-manager
    protocol and ``update(n)``, so implementing those four things avoids any
    dependency on tqdm's rendering internals. ``disable`` is accepted and
    deliberately ignored: whisper sets it whenever ``verbose`` is not False, but
    the position report is wanted alongside the segment text, not instead of it.
    """

    def __init__(
        self,
        total: Optional[int] = None,
        unit: str = "frames",
        disable: bool = False,
        interval: float = DEFAULT_PROGRESS_INTERVAL,
        stream: Optional[IO[str]] = None,
    ) -> None:
        self.total = total or 0
        self.n = 0
        self.interval = interval
        self._stream = stream
        self.total_seconds = self.total * FRAME_SECONDS
        self._started = time.monotonic()
        self._last_report = 0.0

    @property
    def stream(self) -> IO[str]:
        # Resolved late so a stdout swapped in by redirect_to_log is honoured.
        return self._stream if self._stream is not None else sys.stdout

    def __enter__(self) -> AudioProgress:
        return self

    def __exit__(self, exc_type: object, *exc_info: object) -> bool:
        if exc_type is None:
            # whisper's final window routinely stops a few frames short of
            # content_frames, so a completed run would otherwise sign off at
            # ~90%. On a clean exit the audio *was* covered; say so.
            self.n = self.total
        self._report(final=True)
        return False

    def update(self, n: int = 1) -> None:
        self.n += n
        now = time.monotonic()
        if now - self._last_report >= self.interval:
            self._last_report = now
            self._report()

    def _report(self, final: bool = False) -> None:
        position = min(self.n, self.total) * FRAME_SECONDS
        elapsed = time.monotonic() - self._started
        line = (
            f"[progress] {format_timestamp(position)} / "
            f"{format_timestamp(self.total_seconds)}"
        )
        if self.total_seconds:
            line += f" ({position / self.total_seconds * 100:5.1f}%)"
        # Speed is audio-seconds per wall-second; ETA extrapolates from it.
        if elapsed > 0 and position > 0:
            speed = position / elapsed
            line += f"  {speed:.1f}x"
            if not final and self.total_seconds > position:
                line += f"  eta {format_timestamp((self.total_seconds - position) / speed)}"
        print(line, file=self.stream, flush=True)


@contextmanager
def progress_reporting(
    interval: float, stream: Optional[IO[str]] = None
) -> Generator[None, None, None]:
    """Swap whisper's tqdm for :class:`AudioProgress` inside the block.

    whisper resolves the bar as ``tqdm.tqdm(...)`` against its own module-level
    import, so replacing that attribute is enough. Non-positive ``interval``
    leaves whisper untouched.
    """
    if interval <= 0:
        yield
        return

    # Fetched via importlib, not `import whisper.transcribe as ...`: the whisper
    # package re-exports the transcribe *function* under that same name, so the
    # plain import binds the function and not the module holding the tqdm symbol.
    whisper_transcribe = importlib.import_module("whisper.transcribe")

    original = whisper_transcribe.tqdm
    factory = functools.partial(AudioProgress, interval=interval, stream=stream)
    whisper_transcribe.tqdm = SimpleNamespace(tqdm=factory)
    try:
        yield
    finally:
        whisper_transcribe.tqdm = original


def resolve_log_path(log_file: Optional[str], output_dir: str, file_base: str) -> str:
    """Resolve the log destination; a directory argument gets the default name."""
    default_name = f"log_{file_base}.txt"
    if not log_file:
        return os.path.join(output_dir, default_name)
    expanded = os.path.abspath(os.path.expanduser(log_file))
    if os.path.isdir(expanded):
        return os.path.join(expanded, default_name)
    return expanded


def validate_input(video_path: str) -> str:
    """Return the absolute input path, or raise with an actionable message."""
    path = os.path.abspath(os.path.expanduser(video_path))
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    if not os.path.isfile(path):
        raise IsADirectoryError(f"Input path is not a file: {path}")
    try:
        with open(path, "rb") as f:
            f.read(1)
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot read {path}: {exc.strerror}. On macOS grant your terminal "
            "access to this folder (System Settings > Privacy & Security > "
            "Files and Folders / Full Disk Access), or move the file outside a "
            "protected folder such as Downloads/Desktop/Documents."
        ) from exc
    return path


def select_fp16() -> bool:
    """FP16 is only safe on CUDA; CPU/MPS runs fall back to FP32."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def transcribe_to_srt(
    video_path: str,
    language: Optional[str] = DEFAULT_LANGUAGE,
    model_size: str = DEFAULT_MODEL,
    log_file: Optional[str] = None,
    progress_interval: float = DEFAULT_PROGRESS_INTERVAL,
) -> str:
    """Transcribe ``video_path`` and write an ``.srt`` next to it. Returns srt path.

    ``language`` takes an ISO code, or ``"auto"``/``None`` to let whisper detect it.
    """
    path = validate_input(video_path)
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH. Install it (brew install ffmpeg).")
    if model_size not in MODEL_SIZES:
        raise ValueError(f"Unknown model '{model_size}'. Choose one of: {', '.join(MODEL_SIZES)}")

    # Normalise here as well as in main(), so library callers can pass "auto".
    if language is not None and language.lower() == "auto":
        language = None

    output_dir = os.path.dirname(path)
    file_base = os.path.splitext(os.path.basename(path))[0]
    log_path = resolve_log_path(log_file, output_dir, file_base) if log_file is not None else None
    if log_path:
        print(f"Logging enabled. Log file: {log_path}")

    with redirect_to_log(log_path):
        print(f"Loading Whisper model ({model_size})...")
        model = whisper.load_model(model_size)

        print(
            f"Transcribing: {os.path.basename(path)} "
            f"[language: {language or 'auto-detect'}]"
        )
        with progress_reporting(progress_interval):
            result = model.transcribe(
                path,
                language=language,
                verbose=True,
                fp16=select_fp16(),
            )

        writer = get_writer("srt", output_dir)
        writer(result, path)

        srt_path = os.path.join(output_dir, f"{file_base}.srt")
        print(f"\n✅ Done! Subtitles saved to: {srt_path}")
        return srt_path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SRT subtitles from an MP4 file using OpenAI Whisper."
    )
    parser.add_argument("input_file", help="Path to the input MP4 file")
    parser.add_argument(
        "-l",
        "--language",
        default=DEFAULT_LANGUAGE,
        help=(
            "Transcription language code (e.g. 'it', 'en'), or 'auto' to detect. "
            f"Default: {DEFAULT_LANGUAGE}"
        ),
    )
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        choices=MODEL_SIZES,
        help=f"Whisper model size. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=DEFAULT_PROGRESS_INTERVAL,
        metavar="SECONDS",
        help=(
            "How often to print transcription position as 'mm:ss / mm:ss'. "
            f"0 restores whisper's own bar. Default: {DEFAULT_PROGRESS_INTERVAL:g}"
        ),
    )
    parser.add_argument(
        "--log",
        choices=["y", "n"],
        default="n",
        help="Mirror transcription output to a log file (y/n). Default: n",
    )
    parser.add_argument(
        "--log_file",
        help=(
            "Log destination. A directory gets log_{video_name}.txt; a file path is "
            "used verbatim. Defaults to the input folder. Requires --log y."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    language = None if args.language.lower() == "auto" else args.language
    log_file: Optional[str] = None
    if args.log == "y":
        log_file = args.log_file or ""
    elif args.log_file:
        print("Warning: --log_file ignored because --log is 'n'.", file=sys.stderr)

    try:
        transcribe_to_srt(
            args.input_file, language, args.model, log_file, args.progress_interval
        )
    except (FileNotFoundError, IsADirectoryError, PermissionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
