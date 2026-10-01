"""ROS-independent sorting state machine. All methods run on supervisor thread."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sqlite3

COLORS = {'RED': 1, 'YELLOW': 2}
STATES = {'RED', 'YELLOW', 'NO_COLOR', 'WAIT', 'MIXED'}


@dataclass
class Settings:
    empty_seconds: float = 3.0
    settle_seconds: float = 0.5
    camera_timeout: float = 1.0
    robot_timeout: float = 3.0
    ack_timeout: float = 10.0
    motion_timeout: float = 120.0
    ready_timeout: float = 10.0
    scene_timeout: float = 60.0
    batch_timeout: float = 1800.0
    priority: str = 'ABCD'

    def __post_init__(self):
        for name, value in vars(self).items():
            if name != 'priority' and (not math.isfinite(value) or value <= 0):
                raise ValueError(f'{name} must be finite and positive')
        if sorted(self.priority) != list('ABCD'):
            raise ValueError('priority must be a permutation of ABCD')


class Journal:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY,batch TEXT,result TEXT,red INTEGER,yellow INTEGER,error TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS fault (id INTEGER PRIMARY KEY CHECK(id=1), code TEXT)')
        self.db.execute("INSERT OR IGNORE INTO fault VALUES (1,'')")
        self.db.execute('CREATE TABLE IF NOT EXISTS sequence (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER)')
        self.db.execute('INSERT OR IGNORE INTO sequence VALUES (1,0)')
        self.interrupted = bool(self.db.execute("SELECT 1 FROM tasks WHERE result='RUNNING'").fetchone())
        self.db.execute("UPDATE tasks SET result='FAILED',error='PROCESS_RESTART' WHERE result='RUNNING'")
        if self.interrupted: self.db.execute("UPDATE fault SET code='PROCESS_RESTART' WHERE id=1")
        self.fault = self.db.execute('SELECT code FROM fault WHERE id=1').fetchone()[0]
        self.db.commit()

    def set_fault(self, code):
        self.db.execute('UPDATE fault SET code=? WHERE id=1',(code,))
        self.db.commit()
        self.fault=code

    def has(self, task):
        return self.db.execute('SELECT 1 FROM tasks WHERE id=?', (task,)).fetchone() is not None

    def start(self, task, batch):
        self.db.execute('INSERT INTO tasks VALUES (?,?,?,0,0,?)', (task, batch, 'RUNNING', 'NONE'))
        self.db.commit()

    def job(self):
        with self.db:
            value = self.db.execute('SELECT value FROM sequence WHERE id=1').fetchone()[0] + 1
            if value > 65535:
                raise RuntimeError('JOB_ID_EXHAUSTED')
            self.db.execute('UPDATE sequence SET value=? WHERE id=1', (value,))
        return value

    def save(self, task, result, red, yellow, error):
        self.db.execute('UPDATE tasks SET result=?,red=?,yellow=?,error=? WHERE id=?', (result,red,yellow,error,task))
        self.db.commit()


class Supervisor:
    def __init__(self, journal, settings=None):
        self.journal = journal
        self.s = settings or Settings()
        self.phase = 'IDLE'
        self.active = False
        self.task = self.batch = ''
        self.red = self.yellow = 0
        self.command = self.job_id = self.request = 0
        self.result = None
        self.fault = journal.fault
        self.canceling = False
        self.robot = (0,0,0,0)
        self.robot_at = float('-inf')
        self.observation = None
        self.camera_session = None
        self.empty_since = None
        self.started = self.phase_at = self.scan_after = 0.0
        self.last_frame = None
        self.heartbeat = 0

    def camera_good(self, now):
        d = self.observation
        if not isinstance(d, dict): return False
        try:
            stamp = d['monotonic']
            return (type(stamp) in (float,int) and math.isfinite(stamp)
                    and 0 <= now-stamp < self.s.camera_timeout
                    and d['ready'] is True and isinstance(d['camera_session'],str)
                    and bool(d['camera_session']) and type(d['counter']) is int
                    and isinstance(d['zone_states'],dict)
                    and set(d['zone_states']) == set('ABCD')
                    and all(v in STATES for v in d['zone_states'].values()))
        except (KeyError, TypeError): return False

    def robot_good(self, now):
        return 0 <= now-self.robot_at < self.s.robot_timeout

    def ready(self, now):
        return (not self.active and not self.fault and self.camera_good(now)
                and self.robot_good(now) and self.robot[0] == 1 and self.robot[3] == 0)

    def start(self, task, batch, now):
        if not task or not batch or self.journal.has(task) or not self.ready(now):
            return False
        self.journal.start(task,batch)
        self.task,self.batch = task,batch
        self.red=self.yellow=0
        self.active=True; self.canceling=False; self.result=None
        self.started=now; self.camera_session=self.observation['camera_session']
        self._scan(now)
        return True

    def _scan(self, now):
        self.phase='SCANNING'; self.phase_at=now
        self.scan_after=now+self.s.settle_seconds
        self.empty_since=None; self.last_frame=None

    def cancel(self):
        if self.active: self.canceling=True

    def reset_fault(self, now):
        if self.active or not self.camera_good(now) or not self.robot_good(now) or self.robot[0]!=1 or self.robot[3]:
            return False
        self.journal.set_fault('')
        self.fault=''; self.phase='IDLE'
        return True

    def finish(self, code, error='NONE'):
        self.journal.save(self.task,code,self.red,self.yellow,error)
        self.active=False; self.command=self.request=0
        self.phase = {'SUCCESS':'SUCCEEDED','CANCELED':'CANCELED','FAILED':'ERROR'}[code]
        if code=='FAILED':
            self.fault=error
            self.journal.set_fault(error)
        self.result=dict(result_code=code,red_count=self.red,yellow_count=self.yellow,
                         error_code=error,error_message='' if error=='NONE' else error)

    def tick(self, now, observation, events=()):
        self.heartbeat=(self.heartbeat+1)%65536
        self.observation=observation
        for event_at, state, ack, done, error in events:
            self.robot=(state,ack,done,error); self.robot_at=event_at
            if not self.active: continue
            if state==4 or error:
                self.finish('FAILED',f'HCR_ERROR_{error}'); continue
            if self.phase=='WAIT_ACK' and event_at>=self.phase_at and state==2 and ack==self.job_id:
                self.request=0; self.phase='BUSY'; self.phase_at=now
            elif self.phase=='BUSY' and state==3 and ack==self.job_id and done==self.job_id:
                if self.command%10==1: self.red+=1
                else: self.yellow+=1
                self.journal.save(self.task,'RUNNING',self.red,self.yellow,'NONE')
                self.command=self.request=0
                self.phase='WAIT_READY'; self.phase_at=now
            elif self.phase=='WAIT_READY' and state==1:
                if self.canceling: self.finish('CANCELED')
                else: self._scan(now)
            elif self.phase=='BUSY' and state==1:
                self.finish('FAILED','READY_WITHOUT_DONE')
        if not self.active: return
        if now-self.started>self.s.batch_timeout:
            self.finish('FAILED','BATCH_TIMEOUT'); return
        if not self.robot_good(now):
            self.finish('FAILED','HCR_COMM_TIMEOUT'); return
        if not self.camera_good(now):
            self.finish('FAILED','CAMERA_UNAVAILABLE'); return
        if observation['camera_session']!=self.camera_session:
            self.finish('FAILED','CAMERA_SESSION_CHANGED'); return
        if self.canceling and self.phase=='SCANNING':
            self.finish('CANCELED'); return
        limits={'WAIT_ACK':self.s.ack_timeout,'BUSY':self.s.motion_timeout,'WAIT_READY':self.s.ready_timeout}
        if self.phase in limits and now-self.phase_at>limits[self.phase]:
            self.finish('FAILED',self.phase+'_TIMEOUT'); return
        if self.phase!='SCANNING': return
        if self.robot[0]!=1:
            self.finish('FAILED','HCR_NOT_READY'); return
        if now-self.phase_at>self.s.scene_timeout:
            self.finish('FAILED','VISION_UNRESOLVED'); return
        # Only evaluate NEW frames captured after return-to-home settling.
        frame=(observation['camera_session'],observation['counter'],observation['monotonic'])
        if observation['monotonic']<self.scan_after or frame==self.last_frame: return
        self.last_frame=frame
        zones=observation['zone_states']
        for name in self.s.priority:
            if zones[name] in COLORS:
                try: self.job_id=self.journal.job()
                except RuntimeError:
                    self.finish('FAILED','JOB_ID_EXHAUSTED'); return
                self.command=(ord(name)-ord('A')+1)*10+COLORS[zones[name]]
                self.request=1; self.phase='WAIT_ACK'; self.phase_at=now
                self.empty_since=None
                return
        if all(v=='NO_COLOR' for v in zones.values()):
            if self.empty_since is None: self.empty_since=now
            if now-self.empty_since>=self.s.empty_seconds: self.finish('SUCCESS')
        else: self.empty_since=None

    def registers(self):
        return [self.command,self.job_id,self.request,int(self.active),self.heartbeat]

    def view(self, now):
        return dict(phase=self.phase,active=self.active,task_id=self.task if self.active else '',
                    batch_id=self.batch if self.active else '',ready=self.ready(now),
                    command=self.command,job_id=self.job_id,red_count=self.red,yellow_count=self.yellow,
                    total_count=self.red+self.yellow,error=self.fault or 'NONE',
                    robot_state=self.robot[0],robot_connected=self.robot_good(now),
                    canceling=self.canceling)


def read_observation(path):
    try: return json.loads(Path(path).read_text())
    except (OSError, ValueError): return None
