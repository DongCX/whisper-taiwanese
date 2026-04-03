import tempfile
import unittest
from pathlib import Path

from whisper_taiwanese.cli import build_jobs, collect_output_paths, discover_media_files


class CliBatchTests(unittest.TestCase):
    def test_discover_media_files_recurses_and_filters_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.mp4").write_text("", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "b.wav").write_text("", encoding="utf-8")
            (root / "nested" / "notes.txt").write_text("", encoding="utf-8")

            files = discover_media_files(root)

            self.assertEqual(files, [root / "a.mp4", root / "nested" / "b.wav"])

    def test_build_jobs_preserves_relative_directories_for_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "inputs"
            out = Path(temp_dir) / "outputs"
            (root / "nested").mkdir(parents=True)
            (root / "nested" / "episode01.mp4").write_text("", encoding="utf-8")

            jobs = build_jobs(root, out, output_stem=None)

            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].input_file, root / "nested" / "episode01.mp4")
            self.assertEqual(jobs[0].output_dir, out / "nested")
            self.assertEqual(jobs[0].output_stem, "episode01")

    def test_build_jobs_avoids_stem_collisions_in_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "inputs"
            out = Path(temp_dir) / "outputs"
            root.mkdir()
            (root / "clip.mp4").write_text("", encoding="utf-8")
            (root / "clip.wav").write_text("", encoding="utf-8")

            jobs = build_jobs(root, out, output_stem=None)

            self.assertEqual([job.output_stem for job in jobs], ["clip", "clip_wav"])

    def test_discover_media_files_excludes_output_dir_inside_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "inputs"
            output_dir = root / "outputs"
            output_dir.mkdir(parents=True)
            (root / "source.mp4").write_text("", encoding="utf-8")
            (output_dir / "generated.wav").write_text("", encoding="utf-8")

            files = discover_media_files(root, exclude_dirs=[output_dir])

            self.assertEqual(files, [root / "source.mp4"])

    def test_collect_output_paths_includes_wav_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media = root / "demo.mp4"
            media.write_text("", encoding="utf-8")

            jobs = build_jobs(media, root / "outputs", output_stem=None)
            output_paths = collect_output_paths(jobs, keep_wav=True)

            self.assertEqual(len(output_paths), 5)
            self.assertIn(root / "outputs" / "demo.wav", output_paths)


if __name__ == "__main__":
    unittest.main()
