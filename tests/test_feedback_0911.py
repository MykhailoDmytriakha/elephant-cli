"""Feedback 2026-09-11 (a live case): `docs/council/send.html` — the one file under action in
that folder — rendered as `other: send.html`: no link, no description, sitting next to a list of
eighteen images. The owner walks README and TODO only, so the single door to the action was not
reachable from the map. Measured on the live case: 21 non-md files, of which exactly one is a
deliverable — so a line for every one of them would be noise, and a line for none loses the one.

The rule: the map leads to a file of ANY kind the same way. The suffix decides where the
description comes from (md: `summary:` in the body · everything else: the line in Links), not
whether the file may have a line of its own. Described → its own link line inside the folder
block; not described → it stays in the short `other:` list."""
import unittest

from elephant import order
from tests.test_order import Base


class NonMarkdownFileUnderAction(Base):
    def html(self, rel="docs/council/send.html"):
        p = self.case / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<html><body>letter</body></html>", encoding="utf-8")
        return p

    def render(self, extra=()):
        manual = ["- docs/ — рабочие документы", *extra]
        return order.render_links(self.case, False, manual)[0]

    def test_a_described_non_md_file_becomes_a_link_line(self):
        self.html()
        lines = self.render(["- docs/council/send.html — страница рассылки"])
        link = [l for l in lines if "send.html" in l]
        self.assertEqual(len(link), 1, f"the file must appear once, not twice: {link}")
        self.assertIn("[send.html](docs/council/send.html) — страница рассылки", link[0])
        self.assertTrue(link[0].startswith("  "), "the line belongs under its folder, not at the top")
        self.assertLess(lines.index(link[0]), next(i for i, l in enumerate(lines) if l.strip().endswith("img/"))
                        if any(l.strip().endswith("img/") for l in lines) else len(lines),
                        "a described file is a document of the folder: it comes before the sub-folders")

    def test_an_undescribed_non_md_file_stays_in_the_other_list(self):
        self.html()
        lines = self.render()
        self.assertTrue(any(l.strip() == "- other: send.html" for l in lines), lines)

    def test_attachments_are_not_blown_up_into_lines(self):
        for i in range(18):
            self.doc(f"docs/council/img/p{i}.jpg", "x")
        self.html()
        lines = self.render(["- docs/council/send.html — страница рассылки"])
        img = [l for l in lines if "other:" in l and ".jpg" in l]
        self.assertEqual(len(img), 1, "images without a description stay one folded line")
        self.assertIn("… +12", img[0])

    def test_adopt_never_writes_into_a_non_md_file(self):
        p = self.html()
        before = p.read_bytes()
        md = self.doc("docs/note.md", "# Note\n\nbody\n")
        changed = order.adopt(self.case, {"docs/council/send.html": "страница рассылки",
                                          "docs/note.md": "что это"})
        self.assertEqual(changed, ["docs/note.md"])
        self.assertEqual(p.read_bytes(), before, "a non-md file has no body to write a summary into")
        self.assertIn("summary: что это", md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
