"""ROS 2 batch action and status node. Robot motions belong to Rodi."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import uuid

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.task import Future
from smartfarm_interfaces.action import SortBatch
from smartfarm_interfaces.msg import SorterStatus
from std_srvs.srv import Trigger

from .core import Journal, Settings, Supervisor, read_observation
from .modbus import ModbusServer, RegisterBank


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class SorterNode(Node):
    def __init__(self):
        super().__init__('hcr_sorter')
        out=Path.cwd()/'outputs/sorting_station/hcr_runtime'
        defaults=dict(robot_id='sorter_01',modbus_host='192.168.3.2',modbus_port=502,
                      modbus_peer='192.168.3.100',receive_enabled=False,
                      camera_state=str(Path.cwd()/'outputs/sorting_station/hcr_preview/state.json'),
                      journal=str(out/'journal.sqlite3'),runtime_state=str(out/'runtime.json'))
        defaults.update(vars(Settings()))
        for key,value in defaults.items(): self.declare_parameter(key,value)
        def param(key): return self.get_parameter(key).value
        self.robot_id=param('robot_id')
        self.camera_state=Path(param('camera_state')); self.runtime_state=Path(param('runtime_state'))
        self.runtime_state.parent.mkdir(parents=True,exist_ok=True)
        settings=Settings(**{k:param(k) for k in vars(Settings())})
        self.engine=Supervisor(Journal(param('journal')),settings)
        self.bank=RegisterBank()
        self.server=ModbusServer((param('modbus_host'),param('modbus_port')),self.bank,param('modbus_peer'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.boot_id=str(uuid.uuid4()); self.sequence=0
        self.pending=False; self.goal_handle=None; self.waiter=None
        self.last_feedback=0.0; self.last_status=0.0; self.last_signature=None
        self.publisher=self.create_publisher(SorterStatus,f'/{self.robot_id}/status',10)
        self.action=ActionServer(self,SortBatch,f'/{self.robot_id}/sort_batch',
                                 execute_callback=self.execute,goal_callback=self.goal,
                                 cancel_callback=self.cancel,callback_group=ReentrantCallbackGroup())
        self.reset_service=self.create_service(Trigger,f'/{self.robot_id}/reset_fault',self.reset)
        self.timer=self.create_timer(.05,self.tick)
        self.get_logger().info(f'Modbus listening on {param("modbus_host")}:{param("modbus_port")}; waiting for webcam + HCR READY + ROS Goal')

    def goal(self,request):
        valid=(request.robot_id==self.robot_id and 0<len(request.task_id)<=128 and 0<len(request.batch_id)<=128)
        if self.pending or not valid or not self.engine.start(request.task_id,request.batch_id,time.monotonic()):
            self.get_logger().warning('Goal rejected: invalid/duplicate task, busy, fault, camera or HCR not ready')
            return GoalResponse.REJECT
        self.pending=True
        return GoalResponse.ACCEPT

    def cancel(self,handle):
        if not self.engine.active: return CancelResponse.REJECT
        self.engine.cancel()
        return CancelResponse.ACCEPT

    async def execute(self,handle):
        self.goal_handle=handle
        self.waiter=Future()
        if self.engine.result is None: await self.waiter
        data=self.engine.result
        result=SortBatch.Result()
        for key in ('robot_id','task_id','batch_id'): setattr(result,key,getattr(handle.request,key))
        for key,value in data.items(): setattr(result,key,value)
        result.timestamp=timestamp()
        if data['result_code']=='SUCCESS': handle.succeed()
        elif data['result_code']=='CANCELED': handle.canceled()
        else: handle.abort()
        self.goal_handle=None; self.waiter=None; self.pending=False
        return result

    def reset(self,request,response):
        response.success=not self.pending and self.engine.reset_fault(time.monotonic())
        response.message='Fault cleared' if response.success else 'Need fresh camera, HCR READY, no error and no active action'
        return response

    def tick(self):
        events,overflow=self.bank.drain()
        observation=read_observation(self.camera_state)
        # Read the frame before sampling time: an atomic camera update between
        # those operations must not make a fresh frame appear to be in the future.
        now=time.monotonic()
        if overflow and self.engine.active: self.engine.finish('FAILED','MODBUS_EVENT_OVERFLOW')
        self.engine.tick(now,observation,events)
        self.bank.update(self.engine.registers())
        view=self.engine.view(now)
        view['camera_ready']=self.engine.camera_good(now)
        try:
            view['camera_age_seconds']=now-observation['monotonic']
        except (TypeError,KeyError):
            view['camera_age_seconds']=None
        view['monotonic']=now; view['timestamp']=timestamp()
        temp=self.runtime_state.with_suffix('.tmp')
        temp.write_text(json.dumps(view)); os.replace(temp,self.runtime_state)
        signature=(self.engine.phase,self.engine.red,self.engine.yellow,self.engine.canceling)
        if self.goal_handle is not None and (now-self.last_feedback>=1 or signature!=self.last_signature):
            feedback=SortBatch.Feedback()
            for key in ('robot_id','task_id','batch_id'): setattr(feedback,key,getattr(self.goal_handle.request,key))
            feedback.phase='CANCEL_PENDING_'+self.engine.phase if self.engine.canceling and self.engine.active else self.engine.phase
            feedback.red_count=self.engine.red; feedback.yellow_count=self.engine.yellow
            feedback.timestamp=timestamp(); self.goal_handle.publish_feedback(feedback)
            self.last_feedback=now
        self.last_signature=signature
        if now-self.last_status>=1:
            status=SorterStatus()
            status.robot_id=self.robot_id; status.current_task_id=view['task_id']; status.current_batch_id=view['batch_id']
            status.state='ERROR' if self.engine.fault else 'SORTING' if self.engine.active else 'IDLE'
            status.ready=view['ready'] and not self.pending
            status.receive_ready=status.ready and self.get_parameter('receive_enabled').value
            status.error_code=self.engine.fault or 'NONE'; status.error_message=self.engine.fault
            status.boot_id=self.boot_id; self.sequence+=1; status.sequence=self.sequence; status.timestamp=timestamp()
            self.publisher.publish(status); self.last_status=now
        if self.engine.result is not None and self.waiter is not None and not self.waiter.done():
            self.waiter.set_result(True)

    def close(self):
        self.timer.cancel()
        if self.engine.active: self.engine.finish('FAILED','PROCESS_SHUTDOWN')
        self.bank.update([0]*5)
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)
        self.engine.journal.db.close()
        self.action.destroy()
        self.destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node=None
    try:
        node=SorterNode()
        rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        if node is not None: node.close()
        if rclpy.ok(): rclpy.shutdown()
