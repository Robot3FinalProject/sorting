"""Interactive OMX-L -> OMX-F collection into a local LeRobot dataset (RGB)."""
from __future__ import annotations

import argparse
import json
import math
import select
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOINTS = tuple(x + '.pos' for x in (
    'shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper'))


def bounded_action(request, observation, previous, dt, rate=40.0, max_error=5.0):
    """LeRobot normalized units; bound both command slew and tracking error."""
    result = {}
    for key in JOINTS:
        values = (request[key], observation[key], previous[key])
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError(f'Non-finite joint value: {key}')
        low, high = (0.0, 100.0) if key == 'gripper.pos' else (-100.0, 100.0)
        target = max(low, min(high, float(request[key])))
        step = rate * min(dt, 0.05)
        target = max(previous[key] - step, min(previous[key] + step, target))
        result[key] = max(observation[key] - max_error,
                          min(observation[key] + max_error, target))
    return result


def color_for(mode, saved):
    return ('red' if saved % 2 == 0 else 'yellow') if mode == 'alternate' else mode


def features_for(cameras):
    features = {
        'observation.state': {'dtype': 'float32', 'shape': (6,), 'names': list(JOINTS)},
        'action': {'dtype': 'float32', 'shape': (6,), 'names': list(JOINTS)},
        'observation.wall_time': {'dtype': 'float32', 'shape': (1,), 'names': ['seconds_since_start']},
    }
    for name, cfg in cameras.items():
        features[f'observation.images.{name}'] = {
            'dtype': 'image', 'shape': (cfg.height, cfg.width, 3),
            'names': ['height', 'width', 'channels']}
    return features


def camera_configs(path, fps):
    from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
    specs = json.loads(Path(path).read_text())
    if not isinstance(specs, dict) or not specs:
        raise ValueError('At least one RGB camera is required')
    configs = {}
    for name, original in specs.items():
        spec = dict(original)
        kind = spec.pop('type')
        if spec.get('use_depth', False):
            raise ValueError('This collector stores RGB only; depth is not silently discarded')
        spec.setdefault('fps', fps)
        spec.setdefault('width', 640)
        spec.setdefault('height', 480)
        if spec.get('color_mode', 'rgb') != 'rgb':
            raise ValueError('Camera color_mode must be rgb')
        if kind == 'intelrealsense':
            from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
            cls = RealSenseCameraConfig
        elif kind == 'opencv':
            cls = OpenCVCameraConfig
        else:
            raise ValueError(f'Unknown camera type: {kind}')
        configs[name] = cls(**spec)
    return configs


def args_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--leader-port', default='/dev/ttyACM0')
    p.add_argument('--follower-port', required=True)
    p.add_argument('--leader-calibration-dir', type=Path)
    p.add_argument('--follower-calibration-dir', type=Path)
    p.add_argument('--leader-id', default='omx_leader_arm')
    p.add_argument('--follower-id', default='omx_follower_arm')
    p.add_argument('--cameras', required=True, help='JSON camera mapping')
    p.add_argument('--episodes', type=int, default=20)
    p.add_argument('--color', choices=['red', 'yellow', 'alternate'], default='alternate')
    p.add_argument('--fps', type=int, default=30)
    p.add_argument('--max-seconds', type=float, default=120)
    p.add_argument('--rate', type=float, default=40, help='Normalized target units/second')
    p.add_argument('--max-error', type=float, default=5, help='Normalized target-feedback bound')
    p.add_argument('--root', type=Path)
    p.add_argument('--repo-id', default='local/omx_real_sorting')
    p.add_argument('--no-preview', action='store_true')
    p.add_argument('--check', action='store_true', help='Validate imports/config/devices without connecting motors')
    return p


def main():
    args = args_parser().parse_args()
    if not all(math.isfinite(v) and v > 0 for v in
               (args.fps, args.episodes, args.max_seconds, args.rate, args.max_error)):
        raise ValueError('Numeric collection settings must be positive and finite')
    if Path(args.leader_port).resolve() == Path(args.follower_port).resolve():
        raise ValueError('Leader and follower must use different serial ports')
    import numpy as np
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from lerobot.robots.omx_follower.config_omx_follower import OmxFollowerConfig
    from lerobot.robots.omx_follower.omx_follower import OmxFollower
    from lerobot.teleoperators.omx_leader.config_omx_leader import OmxLeaderConfig
    from lerobot.teleoperators.omx_leader.omx_leader import OmxLeader

    cameras = camera_configs(args.cameras, args.fps)
    root = args.root or ROOT / 'outputs/sorting_station/real_demos' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    root = root.resolve()
    if not root.is_relative_to((ROOT / 'outputs/sorting_station').resolve()):
        raise ValueError('Dataset root must be under outputs/sorting_station')
    if root.exists():
        raise ValueError('Use a new dataset root; existing episodes are never overwritten')
    missing = [p for p in (args.leader_port, args.follower_port) if not Path(p).exists()]
    if missing:
        raise ValueError(f'Serial devices missing: {missing}')
    follower = OmxFollower(OmxFollowerConfig(port=args.follower_port, id=args.follower_id, calibration_dir=args.follower_calibration_dir,
        cameras=cameras, disable_torque_on_disconnect=False))
    leader = OmxLeader(OmxLeaderConfig(port=args.leader_port, id=args.leader_id, calibration_dir=args.leader_calibration_dir))
    if not follower.calibration or not leader.calibration:
        raise ValueError('Existing LeRobot calibration required for both IDs; calibrate separately first')
    if args.check:
        print(f'Config/import/device-path check OK. No motor connection. Output: {root}')
        return
    if not sys.stdin.isatty():
        raise ValueError('Run in an interactive terminal')
    cv2 = None
    if not args.no_preview:
        import cv2
        gui_line = next((line.strip() for line in cv2.getBuildInformation().splitlines() if 'GUI:' in line), '')
        if 'NONE' in gui_line:
            raise RuntimeError('OpenCV has no GUI. Run scripts/setup.sh or use --no-preview.')
    dataset = None
    following = False
    state = 'READY'
    saved = 0
    stopping = False
    previous = None
    enabled = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        # Connect without stock configure/calibrate: preserve existing motor modes,
        # gains, currents and offsets. Validate the factory/previous LeRobot setup.
        for robot in (leader, follower):
            robot.bus.connect()
            if not robot.is_calibrated:
                raise ValueError(f'{robot.name}: motor/file calibration mismatch; calibrate separately')
            for motor in robot.bus.motors:
                expected = 5 if motor == 'gripper' else 4
                if robot.bus.read('Operating_Mode', motor, normalize=False) != expected:
                    raise ValueError(f'{robot.name}/{motor}: expected existing mode {expected}; use LeRobot setup first')
        for motor in leader.bus.motors:
            if motor != 'gripper' and leader.bus.read('Torque_Enable', motor, normalize=False):
                raise ValueError('Leader arm torque must already be off for hand guidance')
        for cam in follower.cameras.values():
            cam.connect()
        dataset = LeRobotDataset.create(repo_id=args.repo_id, root=root, fps=args.fps,
            robot_type='omx_follower', features=features_for(cameras), use_videos=False,
            image_writer_threads=4)
        (root / 'collection_config.json').write_text(json.dumps({
            **vars(args), 'root': str(root), 'cameras': json.loads(Path(args.cameras).read_text()),
            'units': 'LeRobot RANGE_M100_100 arm / RANGE_0_100 gripper',
            'success': 'operator confirmed', 'exit_torque': 'preserve',
            'time_note': 'timestamp is nominal FPS; observation.wall_time is host elapsed time; cameras are not hardware synchronized'
        }, default=str, indent=2))
        print('\nCommands: f=follow/hold, SPACE or s=start/stop, y=save success, n=discard/retry, q=quit')
        print('Terminal commands need Enter; preview keys do not. Align leader with follower before f.')
        print('READY/REVIEW hold position. Exit preserves torque; support the arm before power-off.')
        last_tick = time.monotonic()
        start = last_tick
        next_tick = last_tick
        last_report = 0.0
        while not stopping and saved < args.episodes:
            tick = time.monotonic()
            dt = tick - last_tick
            last_tick = tick
            obs = {f'{k}.pos': v for k, v in follower.bus.sync_read('Present_Position', num_retry=2).items()}
            for name, cam in follower.cameras.items():
                obs[name] = cam.read_latest()
            request = leader.get_action()
            command = ''
            if select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline()
                if line == '':
                    break
                command = line.strip().lower() or 's'
            color = color_for(args.color, saved)
            if cv2 is not None:
                for name in cameras:
                    display = cv2.cvtColor(obs[name], cv2.COLOR_RGB2BGR)
                    cv2.putText(display, f'{state} {color} {saved}/{args.episodes} follow={following}',
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 255, 0), 1)
                    cv2.imshow(name, display)
                key = cv2.waitKey(1) & 0xff
                if key != 255:
                    command = 's' if key == 32 else chr(key).lower()
                if any(cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) < 1 for name in cameras):
                    break
            if command == 'q':
                break
            if command == 'f' and state == 'READY':
                if following:
                    following = False
                elif (time.monotonic() - tick <= .25 and
                      all(math.isfinite(float(request[k])) and math.isfinite(float(obs[k])) for k in JOINTS) and
                      max(abs(request[k] - obs[k]) for k in JOINTS) <= args.max_error):
                    previous = {k: float(obs[k]) for k in JOINTS}
                    follower.send_action(previous)
                    follower.bus.enable_torque()
                    enabled = True
                    following = True
                else:
                    print('Align leader first. Differences:', {k: round(request[k]-obs[k], 1) for k in JOINTS})
            if command == 's' and state == 'READY' and following:
                state = 'RECORDING'
                start = tick
                print(f'RECORDING {color}: SPACE/s ends episode')
            elif state == 'RECORDING' and (command == 's' or tick - start >= args.max_seconds):
                state, following = 'REVIEW', False
                print('Save successful demonstration? [Y/n] (y=save, n=discard; follower held)')
            if state == 'REVIEW' and command in ('y', 'n'):
                if command == 'y' and dataset.episode_buffer['size']:
                    dataset.save_episode()
                    saved += 1
                    print(f'Saved {saved}/{args.episodes}: {root}')
                else:
                    dataset.clear_episode_buffer()
                    print('Discarded; retry the same color')
                state = 'READY'
                print('READY: reposition using f, then SPACE/s to record')
            if following:
                if dt > .25 or time.monotonic() - tick > .25:
                    following = False
                    state = 'REVIEW' if state == 'RECORDING' else 'READY'
                    print('Control delay >250 ms: following held; review/retry episode')
                else:
                    target = bounded_action(request, obs, previous, dt, args.rate, args.max_error)
                    previous = follower.send_action(target)
                    if state == 'RECORDING':
                        frame = {'observation.state': np.array([obs[k] for k in JOINTS], dtype=np.float32),
                            'action': np.array([previous[k] for k in JOINTS], dtype=np.float32),
                            'observation.wall_time': np.array([tick-start], dtype=np.float32),
                            'task': f'Pick the {color} pepper and place it on the {"left" if color == "red" else "right"} chute into storage.'}
                        frame.update({f'observation.images.{name}': obs[name].copy() for name in cameras})
                        dataset.add_frame(frame)
            if tick - last_report >= 2:
                print(f'[{state}] color={color} saved={saved} frames={dataset.episode_buffer["size"]} follow={following}')
                last_report = tick
            next_tick = max(next_tick + 1 / args.fps, time.monotonic())
            time.sleep(max(0, next_tick-time.monotonic()))
    finally:
        # Hold measured position before closing communication, if we armed it.
        if enabled and follower.bus.is_connected:
            try:
                position = follower.bus.sync_read('Present_Position')
                follower.bus.sync_write('Goal_Position', position)
            except Exception as exc:
                print(f'Could not hold measured position: {exc}', file=sys.stderr)
        # No automatic HOME or torque-off: either can move/drop a loaded arm.
        for robot in (follower, leader):
            if robot.bus.is_connected:
                try:
                    robot.bus.disconnect(disable_torque=False)
                except Exception as exc:
                    print(f'Disconnect error: {exc}', file=sys.stderr)
        for cam in follower.cameras.values():
            if cam.is_connected:
                try:
                    cam.disconnect()
                except Exception as exc:
                    print(f'Camera disconnect error: {exc}', file=sys.stderr)
        if dataset is not None:
            dataset.clear_episode_buffer()
            dataset.finalize()
            if dataset.image_writer is not None:
                dataset.stop_image_writer()
        if cv2 is not None:
            cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
