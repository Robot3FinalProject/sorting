"""D435 color-only capture using the official SDK (no depth stream)."""
import numpy as np


def choose_device(devices, serial=None):
    """Select from (name, serial) records; never silently choose another camera."""
    matches = [d for d in devices if 'D435' in d[0] and (serial is None or d[1] == serial)]
    if not matches:
        raise RuntimeError(f'No matching D435 connected (serial={serial or "auto"}); found {devices}')
    if len(matches) != 1:
        raise RuntimeError('Multiple D435 cameras connected; specify --serial. Found: ' + str(matches))
    return matches[0]


class RealSenseCamera:
    def __init__(self, serial=None, width=640, height=480, fps=30):
        try:
            import pyrealsense2 as rs
        except ImportError as exc:
            raise RuntimeError('RealSense SDK missing. Use bash src/sorting_station/hcr/run_d435_preview.sh') from exc
        self.context = rs.context()
        devices = list(self.context.query_devices())
        name, self.serial = choose_device([
            (d.get_info(rs.camera_info.name), d.get_info(rs.camera_info.serial_number))
            for d in devices], serial)
        self.pipeline = rs.pipeline(self.context)
        self.started = False
        config = rs.config()
        config.enable_device(self.serial)
        config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        try:
            profile = self.pipeline.start(config)
            self.started = True
            device = profile.get_device()
            usb = device.get_info(rs.camera_info.usb_type_descriptor)
            self.source = f'realsense:{self.serial}:color:bgr8:{width}x{height}:{fps}'
            print(f'{name} serial={self.serial} USB={usb} COLOR BGR8 {width}x{height}@{fps}', flush=True)
        except Exception:
            self.release()
            raise

    def read(self):
        frames = self.pipeline.wait_for_frames(timeout_ms=1500)
        color = frames.get_color_frame()
        if not color:
            return False, None
        # Copy before SDK frame ownership expires.
        return True, np.asanyarray(color.get_data()).copy()

    def release(self):
        if self.started:
            self.pipeline.stop()
            self.started = False
