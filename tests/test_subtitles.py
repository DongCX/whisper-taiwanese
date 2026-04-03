import unittest

from whisper_taiwanese.subtitles import build_cues, format_timestamp, render_srt, wrap_subtitle_text
from whisper_taiwanese.types import TranscriptChunk


class SubtitleTests(unittest.TestCase):
    def test_format_timestamp_for_srt(self) -> None:
        self.assertEqual(format_timestamp(65.432, "srt"), "00:01:05,432")

    def test_wrap_subtitle_text_for_cjk(self) -> None:
        text = "這是一段比較長的台語字幕內容需要切成兩行顯示"
        self.assertEqual(
            wrap_subtitle_text(text, max_chars=10, max_lines=2),
            [
                "這是一段比較長的台語",
                "字幕內容需要切成兩行顯示",
            ],
        )

    def test_build_cues_merges_nearby_chunks(self) -> None:
        chunks = [
            TranscriptChunk(start=0.0, end=1.0, text="逐字稿"),
            TranscriptChunk(start=1.1, end=2.0, text="測試"),
            TranscriptChunk(start=3.5, end=4.0, text="下一句"),
        ]
        cues = build_cues(chunks, max_chars=10, max_duration=6.0, silence_gap=0.9)
        self.assertEqual([cue.text for cue in cues], ["逐字稿測試", "下一句"])

    def test_render_srt_contains_indices_and_timestamps(self) -> None:
        srt = render_srt(
            build_cues([TranscriptChunk(start=0.0, end=2.5, text="台語字幕測試")]),
            max_chars=22,
        )
        self.assertIn("1", srt)
        self.assertIn("00:00:00,000 --> 00:00:02,500", srt)
        self.assertIn("台語字幕測試", srt)


if __name__ == "__main__":
    unittest.main()
