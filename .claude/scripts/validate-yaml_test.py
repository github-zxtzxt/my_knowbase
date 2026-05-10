"""Tests for validate-yaml.py. Run with: python .claude/scripts/validate-yaml_test.py"""
import tempfile, os, subprocess, sys, unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / 'validate-yaml.py'


class TestValidateYaml(unittest.TestCase):
    def _run(self, tmp_path, files):
        wiki = tmp_path / 'wiki'
        wiki.mkdir()
        for relpath, content in files.items():
            full = wiki / relpath
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding='utf-8')
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(tmp_path),
            capture_output=True, text=True
        )

    def test_list_format_related(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(Path(d), {'test.md': '---\ntags: [a]\nrelated:\n  - "[[p1]]"\n  - "[[p2]]"\n---\n# Hello\n'})
        self.assertEqual(r.returncode, 0)
        self.assertIn('Invalid: 0', r.stdout)

    def test_bare_wikilinks_with_comma(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(Path(d), {'test.md': '---\ntags: [a]\nrelated: [[p1]], [[p2]]\n---\n'})
        self.assertEqual(r.returncode, 1)
        self.assertIn('Invalid: 1', r.stdout)

    def test_no_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(Path(d), {'test.md': '# Just a heading\n'})
        self.assertEqual(r.returncode, 0)

    def test_mixed_valid_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(Path(d), {
                'good.md': '---\ntags: [a]\n---\n',
                'bad.md': '---\ntags: [a]\nrelated: [[a]], [[b]]\n---\n',
                'also_good.md': '---\nsource: "[[x]]"\n---\n',
            })
        self.assertEqual(r.returncode, 1)
        self.assertIn('Invalid: 1', r.stdout)

    def test_deep_dirs_all_valid(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(Path(d), {
                'concepts/a.md': '---\ntags: [x]\n---\n',
                'errors/b.md': '---\ntags: [y]\nrelated: "[[z]]"\n---\n',
            })
        self.assertEqual(r.returncode, 0)
        self.assertIn('Valid: 2', r.stdout)

    def test_list_format_tags(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(Path(d), {'test.md': '---\ntags:\n  - tag1\n  - tag2\n---\n# Hello\n'})
        self.assertEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()
