import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/sorting_station'))
from collect_real_pepper_demos import JOINTS, bounded_action, color_for

class RealCollectionTests(unittest.TestCase):
    def test_no_jump(self):
        current = dict.fromkeys(JOINTS, 0.)
        result = bounded_action(dict.fromkeys(JOINTS, 100.), current, current, 1/30)
        self.assertLessEqual(max(result.values()), 40/30)
    def test_tracking_error(self):
        result = bounded_action(dict.fromkeys(JOINTS, 100.), dict.fromkeys(JOINTS, 0.),
                                dict.fromkeys(JOINTS, 80.), 1.)
        self.assertLessEqual(max(result.values()), 5.)
    def test_nan_refused(self):
        with self.assertRaises(ValueError):
            bounded_action(dict.fromkeys(JOINTS, float('nan')), dict.fromkeys(JOINTS, 0.),
                           dict.fromkeys(JOINTS, 0.), .03)
    def test_color_on_saved_count(self):
        self.assertEqual([color_for('alternate', i) for i in range(3)], ['red','yellow','red'])

if __name__ == '__main__':
    unittest.main()
