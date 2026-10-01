#!/usr/bin/env python3
"""Interactive four-zone color preview. Writes dummy observations, never START."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs/sorting_station/hcr_preview'
NAMES = 'ABCD'


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    os.replace(temp, path)


def classify(roi, minimum=.08, saturation=90, brightness=60):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    valid = (hsv[:, :, 1] >= saturation) & (hsv[:, :, 2] >= brightness)
    hue = hsv[:, :, 0]
    red = valid & ((hue <= 10) | (hue >= 170))
    yellow = valid & (hue >= 18) & (hue <= 38)
    kernel = np.ones((3, 3), np.uint8)
    ratios = []
    for mask in (red, yellow):
        mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        ratios.append(float(np.count_nonzero(mask)) / mask.size)
    r, y = ratios
    if r >= minimum and y >= minimum:
        state = 'MIXED'
    elif r >= minimum:
        state = 'RED'
    elif y >= minimum:
        state = 'YELLOW'
    else:
        state = 'NO_COLOR'  # Not proof of an empty region.
    return state, r, y


class Stable:
    def __init__(self, seconds=.3):
        self.seconds = seconds
        self.last = None
        self.since = 0

    def update(self, raw, now):
        if raw != self.last:
            self.last, self.since = raw, now
        return raw if now - self.since >= self.seconds else 'WAIT'


def select(states, priority='ABCD'):
    for name in priority:
        if states.get(name) in ('RED', 'YELLOW'):
            zone = NAMES.index(name) + 1
            color = 1 if states[name] == 'RED' else 2
            return zone, color
    return 0, 0


def validate_rois(rois, width, height):
    if not isinstance(rois, dict) or set(rois) - set(NAMES):
        raise ValueError('Invalid ROI names')
    for rect in rois.values():
        if len(rect) != 4 or any(type(v) is not int for v in rect):
            raise ValueError('ROI must contain four integers')
        x, y, w, h = rect
        if x < 0 or y < 0 or w < 5 or h < 5 or x+w > width or y+h > height:
            raise ValueError('ROI is outside frame or too small')
    values = list(rois.values())
    for i, (x,y,w,h) in enumerate(values):
        for a,b,c,d in values[i+1:]:
            if max(x,a) < min(x+w,a+c) and max(y,b) < min(y+h,b+d):
                raise ValueError('ROIs must not overlap')


def render(frame, rois, observations, zone, color, priority, enabled, edit, counter):
    h,w = frame.shape[:2]
    canvas = np.zeros((h+180, max(w, 800), 3), np.uint8)
    canvas[:h,:w] = frame
    for name, (x,y,rw,rh) in rois.items():
        state, red, yellow = observations.get(name, ('WAIT',0,0))
        tint = (0,0,255) if state == 'RED' else (0,255,255) if state == 'YELLOW' else (180,180,180)
        cv2.rectangle(canvas, (x,y), (x+rw,y+rh), tint, 4 if zone == NAMES.index(name)+1 else 1)
        cv2.putText(canvas, f'{name}: {state} R{red:.0%} Y{yellow:.0%}', (x,max(18,y+20)), 0,.45,tint,1)
    chosen = f'{NAMES[zone-1]} / {"RED" if color==1 else "YELLOW"}' if zone else 'NONE'
    lines = [f'VISION | priority: {">".join(priority)} | frame {counter}',
             f'Candidate: {chosen} | register 0 = {zone*10+color} | {"LIVE" if enabled else "PAUSED"}',
             'A/B/C/D: select zone, then mouse drag | S: save | Space: pause | Q: quit',
             f'Editing: {edit or "none"} | All 4 non-overlapping zones required. NO_COLOR does not mean empty.',
             'Camera candidate above. ROS job / robot command shown below when supervisor is online.']
    for i,line in enumerate(lines):
        cv2.putText(canvas,line,(10,h+26+i*30),0,.48,(230,230,230),1)
    return canvas


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera',default='0',help='OpenCV device; use --backend opencv')
    p.add_argument('--backend',choices=('realsense','opencv'),default='realsense')
    p.add_argument('--serial',help='D435 serial; auto-select only if one D435 exists')
    p.add_argument('--width',type=int,default=640)
    p.add_argument('--height',type=int,default=480)
    p.add_argument('--fps',type=int,default=30)
    p.add_argument('--demo',action='store_true',help='Synthetic image, no camera')
    p.add_argument('--priority',default='ABCD')
    p.add_argument('--min-ratio',type=float,default=.08)
    p.add_argument('--stable-seconds',type=float,default=.3)
    p.add_argument('--saturation',type=int,default=90)
    p.add_argument('--brightness',type=int,default=60)
    p.add_argument('--config',type=Path)
    p.add_argument('--state',type=Path,default=OUT/'state.json')
    p.add_argument('--runtime-state',type=Path,default=ROOT/'outputs/sorting_station/hcr_runtime/runtime.json')
    p.add_argument('--headless-frames',type=int,default=0,help='Finite non-GUI smoke test')
    args=p.parse_args()
    args.priority=args.priority.upper()
    if args.config is None:
        args.config=OUT/('demo_zones.json' if args.demo else 'd435_zones.json' if args.backend=='realsense' else 'zones.json')
    if min(args.width,args.height,args.fps)<=0:
        p.error('width, height, fps must be positive')
    if sorted(args.priority)!=list(NAMES) or not 0<args.min_ratio<=1 or not 0<=args.stable_seconds<=10 or not 0<=args.saturation<=255 or not 0<=args.brightness<=255 or args.headless_frames<0:
        p.error('Invalid priority or thresholds')
    rois={}; trackers={n:Stable(args.stable_seconds) for n in NAMES}
    enabled=True; editor={'name':None,'start':None}; shape=None; counter=0; total_frames=0; last=None
    cap=None; window='HCR zone preview'; source='demo' if args.demo else args.camera
    camera_session=str(uuid.uuid4()); latest_states={}; frame_mono=0.0
    atomic_json(args.state,{'timestamp':0,'zone':0,'color':0,'valid':False,'counter':0})
    def publish(zone=0,color=0,stamp=None):
        atomic_json(args.state,dict(timestamp=time.time() if stamp is None else stamp,
                    monotonic=frame_mono, camera_session=camera_session,
                    ready=stamp is not None and enabled and editor['name'] is None and set(rois)==set(NAMES),
                    zone_states=latest_states,zone=zone,color=color,valid=bool(zone),counter=counter))
    def mouse(event,x,y,flags,param):
        if editor['name'] is None or shape is None:
            return
        h,w=shape
        x,y=max(0,min(x,w)),max(0,min(y,h))
        if event==cv2.EVENT_LBUTTONDOWN:
            editor['start']=(x,y)
        elif event==cv2.EVENT_LBUTTONUP and editor['start'] is not None:
            a,b=editor['start']; rect=[min(a,x),min(b,y),abs(x-a),abs(y-b)]
            candidate=dict(rois); candidate[editor['name']]=rect
            try:
                validate_rois(candidate,w,h)
                rois.update(candidate)
                for n in NAMES: trackers[n]=Stable(args.stable_seconds)
                editor['name']=None
            except ValueError as exc: print(exc,flush=True)
            editor['start']=None
    try:
        if not args.demo:
            if args.backend=='realsense':
                from realsense_camera import RealSenseCamera
                cap=RealSenseCamera(args.serial,args.width,args.height,args.fps)
                source=cap.source
                window='D435 '+cap.serial+' | HCR zone preview'
            else:
                cap=cv2.VideoCapture(int(args.camera) if args.camera.isdigit() else args.camera)
                if not cap.isOpened(): raise RuntimeError(f'Cannot open camera {args.camera}')
        if not args.headless_frames:
            cv2.namedWindow(window,cv2.WINDOW_AUTOSIZE); cv2.setMouseCallback(window,mouse)
        while True:
            if args.demo:
                frame=np.full((480,640,3),45,np.uint8)
                cv2.rectangle(frame,(60,70),(200,190),(0,0,255),-1)
                cv2.rectangle(frame,(360,70),(510,190),(0,255,255),-1)
                time.sleep(.03)
            else:
                ok,frame=cap.read()
                if not ok: raise RuntimeError('Camera frame unavailable; output cleared')
            stamp=time.time(); now=time.monotonic(); h,w=frame.shape[:2]
            if shape is None:
                shape=(h,w)
                if args.config.exists():
                    cfg=json.loads(args.config.read_text())
                    if cfg['size']!=[w,h] or cfg['source']!=source:
                        raise ValueError('Saved ROI source/size differs; choose another --config')
                    rois=cfg['rois']; validate_rois(rois,w,h)
                elif args.demo:
                    rois={'A':[20,30,260,190],'B':[320,30,260,190],'C':[20,260,260,190],'D':[320,260,260,190]}
            elif shape!=(h,w): raise RuntimeError('Frame dimensions changed')
            obs={}
            for name,(x,y,rw,rh) in rois.items():
                raw,r,yellow=classify(frame[y:y+rh,x:x+rw],args.min_ratio,args.saturation,args.brightness)
                obs[name]=(trackers[name].update(raw,now),r,yellow)
            ready=enabled and editor['name'] is None and set(rois)==set(NAMES)
            zone,color=select({n:v[0] for n,v in obs.items()},args.priority) if ready else (0,0)
            latest_states={n:v[0] for n,v in obs.items()}; frame_mono=now
            counter=(counter+1)%65536; total_frames+=1; publish(zone,color,stamp)
            if (zone,color)!=last:
                print(f'PREVIEW zone={zone} color={color} code={zone*10+color}',flush=True); last=(zone,color)
            canvas=render(frame,rois,obs,zone,color,args.priority,enabled,editor['name'],counter)
            banner='ROS OFFLINE | camera candidate only'
            try:
                runtime=json.loads(args.runtime_state.read_text())
                if 0<=now-runtime.get('monotonic',0)<2:
                    banner=f"ROS {runtime['phase']} | job {runtime['job_id']} cmd {runtime['command']} | red {runtime['red_count']} yellow {runtime['yellow_count']} | {runtime['error']}"
            except (OSError,ValueError,KeyError,TypeError): pass
            canvas=np.vstack((canvas,np.zeros((40,canvas.shape[1],3),np.uint8)))
            cv2.putText(canvas,banner,(10,canvas.shape[0]-14),0,.45,(100,255,100),1)
            if args.headless_frames:
                if total_frames>=args.headless_frames:
                    args.state.parent.mkdir(parents=True,exist_ok=True)
                    cv2.imwrite(str(args.state.parent/'preview.png'),canvas); break
                continue
            cv2.imshow(window,canvas); key=cv2.waitKey(1)&255
            if key in (27,ord('q')) or cv2.getWindowProperty(window,cv2.WND_PROP_VISIBLE)<1: break
            if key in [ord(n) for n in 'abcdABCD']:
                editor['name']=chr(key).upper(); editor['start']=None; publish()
            elif key==ord(' '):
                enabled=not enabled; publish()
                for n in NAMES: trackers[n]=Stable(args.stable_seconds)
            elif key==ord('s'):
                atomic_json(args.config,dict(size=[w,h],source=source,rois=rois)); print(f'Saved {args.config}',flush=True)
    finally:
        publish()
        if cap is not None: cap.release()
        if not args.headless_frames: cv2.destroyAllWindows()


if __name__=='__main__':
    main()
