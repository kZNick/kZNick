import unittest
import xml.etree.ElementTree as ET
from grow_snake import enhance, head_frames, position, NS, MAX_LENGTH


def fixture(eats=True):
    food = "@keyframes c0{24.99%{fill:var(--c2)}25%,100%{fill:var(--ce)}}@keyframes c1{49.99%{fill:var(--c2)}50%,100%{fill:var(--ce)}}" if eats else ""
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-16 -32 880 192"><style>.s{animation:none 10000ms linear infinite}' + food + '@keyframes s0{0%,100%{transform:translate(0px,-16px)}25%{transform:translate(0px,0px)}50%{transform:translate(16px,0px)}75%{transform:translate(16px,-16px)}}.s.s0{animation-name:s0}</style><rect class="c c0" x="2" y="2"/><rect class="s s0"/></svg>'


class GrowingSnakeTests(unittest.TestCase):
    def test_growth_matches_food_and_preserves_calendar(self):
        root = ET.fromstring(enhance(fixture()))
        parts = root.findall(f'.//{{{NS}}}rect[@class="growing-part"]')
        births = [float(part.get('data-born-at')) for part in parts]
        self.assertEqual(sum(t <= 0 for t in births), 4)
        self.assertEqual(sum(t <= 25 for t in births), 5)
        self.assertEqual(sum(t <= 50 for t in births), 6)
        self.assertEqual(len(root.findall(f'.//{{{NS}}}rect[@class="c c0"]')), 1)
        self.assertNotIn('class="s s0"', ET.tostring(root, encoding='unicode'))

    def test_empty_calendar_stays_at_initial_length(self):
        root = ET.fromstring(enhance(fixture(False)))
        self.assertEqual(root.get('data-final-length'), '4')

    def test_compressed_keyframes_are_sorted_and_interpolated(self):
        css = ET.fromstring(fixture()).find(f'{{{NS}}}style').text
        frames = head_frames(css)
        self.assertEqual([t for t, _ in frames], [0, 25, 50, 75, 100])
        self.assertEqual(position(frames, 37.5, 25), (8, 0))
        self.assertEqual(position(frames, -25, 25), (16, -16))

    def test_rejects_invalid_or_already_processed_svg(self):
        with self.assertRaises(ValueError):
            enhance('<svg xmlns="http://www.w3.org/2000/svg"/>')
        with self.assertRaises(ValueError):
            enhance(enhance(fixture()))

    def test_dense_calendar_keeps_growth_within_limit(self):
        svg = fixture(False).replace('</style>', ''.join(
            f'@keyframes c{i}{{{i / 4 + 1}%,100%{{fill:var(--ce)}}}}'
            for i in range(365)
        ) + '</style>')
        root = ET.fromstring(enhance(svg))
        self.assertEqual(int(root.get('data-final-length')), MAX_LENGTH)


if __name__ == '__main__':
    unittest.main()
