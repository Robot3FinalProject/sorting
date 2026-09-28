"""Dependency and USB inventory only: does not open serial ports or move motors."""
import glob
import importlib
import os
from pathlib import Path
import sys


def main():
    errors = []
    print(f'Python: {sys.version.split()[0]}')
    for name in ('numpy', 'torch', 'datasets', 'dynamixel_sdk', 'pyrealsense2',
                 'lerobot.datasets.lerobot_dataset', 'lerobot.robots.omx_follower.omx_follower',
                 'lerobot.teleoperators.omx_leader.omx_leader'):
        try:
            importlib.import_module(name)
            print(f'OK import {name}')
        except Exception as exc:
            errors.append(name)
            print(f'ERROR {name}: {exc}')
    try:
        import cv2
        gui = next((x.strip() for x in cv2.getBuildInformation().splitlines() if 'GUI:' in x), 'GUI: unknown')
        print(gui)
        if 'NONE' in gui:
            errors.append('OpenCV GUI (rerun setup.sh)')
        if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
            print('No desktop display: use --no-preview or launch from the desktop terminal.')
    except ImportError as exc:
        errors.append(str(exc))
    for pattern in ('/dev/serial/by-id/*', '/dev/v4l/by-id/*'):
        matches = sorted(glob.glob(pattern))
        print(f'{pattern}:')
        for path in matches:
            print(f'  {path} -> {Path(path).resolve()} readable/writable={os.access(path, os.R_OK | os.W_OK)}')
        if not matches:
            print('  (none connected)')
    try:
        import pyrealsense2 as rs
        devices = list(rs.context().query_devices())
        for dev in devices:
            print('RealSense:', dev.get_info(rs.camera_info.name), dev.get_info(rs.camera_info.serial_number))
        if not devices:
            print('No RealSense detected. Check USB cable/power/udev permissions.')
    except ImportError:
        pass
    except Exception as exc:
        print(f'RealSense inventory failed: {exc}')
    print('No motor connection or motion performed. Camera streaming and calibration still need checking.')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
