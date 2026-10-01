import tempfile
from pathlib import Path
import unittest
from hcr_sorting.core import Journal, Settings, Supervisor


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.j=Journal(Path(self.tmp.name)/'journal.db')
        self.e=Supervisor(self.j,Settings(empty_seconds=.3,settle_seconds=.1))
        self.now=10.; self.frame=0
        self.states=dict(A='RED',B='YELLOW',C='NO_COLOR',D='NO_COLOR')
        self.robot=(1,0,0,0)
        self.tick()

    def tearDown(self):
        self.j.db.close(); self.tmp.cleanup()

    def tick(self,dt=.1,events=None,obs=True):
        self.now+=dt;self.frame+=1
        d=dict(monotonic=self.now,ready=True,camera_session='cam1',counter=self.frame,zone_states=self.states.copy()) if obs else None
        self.e.tick(self.now,d,[(self.now,*self.robot)] if events is None else events)

    def start(self):
        self.assertTrue(self.e.start('task','batch',self.now))
        self.tick(.2); self.assertEqual(self.e.phase,'WAIT_ACK')

    def busy(self):
        self.robot=(2,self.e.job_id,0,0);self.tick()
        self.assertEqual(self.e.phase,'BUSY')

    def done(self):
        self.robot=(3,self.e.job_id,self.e.job_id,0);self.tick()
        self.assertEqual(self.e.phase,'WAIT_READY')

    def ready(self):
        self.robot=(1,self.e.job_id,self.e.job_id,0);self.tick()

    def test_no_goal_no_motion(self):
        for _ in range(10):self.tick()
        self.assertEqual(self.e.registers()[:4],[0,0,0,0])

    def test_latch_repeat_a_count_once(self):
        self.start();job1=self.e.job_id;self.busy()
        self.states['A']='NO_COLOR';self.states['D']='RED';self.tick()
        self.assertEqual(self.e.command,11)
        self.done();self.tick();self.tick()
        self.assertEqual(self.e.red,1)
        self.states['A']='RED';self.ready();self.tick(.2)
        self.assertEqual(self.e.command,11);self.assertGreater(self.e.job_id,job1)

    def test_empty_timer_mixed_and_wait(self):
        self.states={n:'NO_COLOR' for n in 'ABCD'}
        self.tick();self.assertTrue(self.e.start('task','batch',self.now))
        self.tick(.2);self.tick(.2)
        self.states['A']='WAIT';self.tick(.1)
        self.states['A']='MIXED';self.tick(.5)
        self.assertIsNone(self.e.result)
        self.states['A']='NO_COLOR';self.tick();self.tick(.4)
        self.assertEqual(self.e.result['result_code'],'SUCCESS')
        self.assertFalse(self.e.start('task','batch',self.now))

    def test_no_busy_no_completion(self):
        self.start();self.robot=(3,self.e.job_id,self.e.job_id,0);self.tick()
        self.assertEqual(self.e.red,0);self.assertEqual(self.e.phase,'WAIT_ACK')
        self.tick(11)
        self.assertEqual(self.e.result['error_code'],'WAIT_ACK_TIMEOUT')

    def test_wrong_done_ignored(self):
        self.start();self.busy()
        self.robot=(3,self.e.job_id,self.e.job_id+1,0);self.tick()
        self.assertEqual(self.e.red,0);self.assertEqual(self.e.phase,'BUSY')

    def test_ready_without_done_fails(self):
        self.start();self.busy();self.robot=(1,self.e.job_id,0,0);self.tick()
        self.assertEqual(self.e.result['error_code'],'READY_WITHOUT_DONE')

    def test_cancel_drain(self):
        self.start();self.e.cancel();self.busy();self.done()
        self.assertIsNone(self.e.result)
        self.ready()
        self.assertEqual(self.e.result['result_code'],'CANCELED');self.assertEqual(self.e.red,1)

    def test_camera_failure_not_empty(self):
        self.start();self.tick(obs=False)
        self.assertEqual(self.e.result['error_code'],'CAMERA_UNAVAILABLE')
        self.assertEqual(self.e.command,0)

    def test_heartbeat_timeout(self):
        self.start();self.tick(4,events=[])
        self.assertEqual(self.e.result['error_code'],'HCR_COMM_TIMEOUT')

    def test_fresh_frame_after_return(self):
        self.start();self.busy();self.done();self.ready()
        self.e.tick(self.now+.5,self.e.observation,[(self.now+.5,*self.robot)])
        self.assertEqual(self.e.phase,'SCANNING')
        self.tick(.6);self.assertEqual(self.e.phase,'WAIT_ACK')

    def test_restart_latched_and_sequence_not_reused(self):
        self.start();job=self.e.job_id
        other=Journal(Path(self.tmp.name)/'journal.db')
        try:
            restarted=Supervisor(other)
            self.assertEqual(restarted.fault,'PROCESS_RESTART')
            self.assertTrue(other.has('task'));self.assertGreater(other.job(),job)
        finally:other.db.close()

    def test_feedback_fast_events_kept(self):
        self.start();j=self.e.job_id
        self.tick(events=[(self.now+.01,2,j,0,0),(self.now+.02,3,j,j,0)])
        self.assertEqual(self.e.red,1);self.assertEqual(self.e.phase,'WAIT_READY')

    def test_fault_survives_restart_and_requires_ready_reset(self):
        self.start();self.tick(obs=False)
        other=Journal(Path(self.tmp.name)/'journal.db')
        try:
            restored=Supervisor(other)
            self.assertEqual(restored.fault,'CAMERA_UNAVAILABLE')
            self.assertFalse(restored.reset_fault(self.now))
        finally:other.db.close()
        self.robot=(1,0,0,0);self.tick()
        self.assertTrue(self.e.reset_fault(self.now))
        self.assertEqual(self.j.fault,'')

    def test_invalid_observation_not_ready(self):
        self.e.observation={'monotonic':float('nan')}
        self.assertFalse(self.e.ready(self.now))


if __name__=='__main__':unittest.main()
