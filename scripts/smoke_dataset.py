"""Hardware-free native LeRobot RGB dataset round-trip test."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/sorting_station'))
from collect_real_pepper_demos import features_for
from lerobot.datasets.lerobot_dataset import LeRobotDataset


def frame(i):
    return {'observation.state': np.zeros(6, dtype=np.float32),
            'action': np.ones(6, dtype=np.float32),
            'observation.wall_time': np.array([i / 30], dtype=np.float32),
            'observation.images.top': np.zeros((16, 16, 3), dtype=np.uint8),
            'observation.images.wrist': np.full((16, 16, 3), 100, dtype=np.uint8),
            'task': 'Sort red pepper left'}


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / 'data'
    ds = LeRobotDataset.create(repo_id='local/smoke', root=root, fps=30,
        robot_type='omx_follower', use_videos=False, image_writer_threads=2,
        features=features_for({n: SimpleNamespace(height=16, width=16) for n in ('top', 'wrist')}))
    # A rejected attempt must not survive into the accepted episode.
    ds.add_frame(frame(0))
    ds.clear_episode_buffer()
    for i in range(3):
        ds.add_frame(frame(i))
    ds.save_episode()
    ds.finalize()
    ds.stop_image_writer()
    read = LeRobotDataset('local/smoke', root=root)
    assert read.num_frames == 3 and read.num_episodes == 1
    assert tuple(read[0]['observation.images.top'].shape) == (3, 16, 16)
    assert read[0]['action'].tolist() == [1.] * 6
    print('PASS: discard, two-camera RGB save, finalize, reload, action and image decoding')
