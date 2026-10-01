"""Actual ROS Action + Modbus loopback integration. No hardware access."""
import json
from pathlib import Path
import tempfile
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from smartfarm_interfaces.action import SortBatch
from smartfarm_interfaces.msg import SorterStatus
from hcr_sorting.node import SorterNode
from hcr_sorting.dummy_control import DummyControl
from hcr_sorting.mock_hcr import Client


def main():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        args=['--ros-args','-p','modbus_host:=127.0.0.1','-p','modbus_port:=0','-p','modbus_peer:=127.0.0.1',
              '-p',f'camera_state:={root / "camera.json"}','-p',f'runtime_state:={root / "runtime.json"}',
              '-p',f'journal:={root / "journal.db"}','-p','empty_seconds:=0.25','-p','settle_seconds:=0.1']
        rclpy.init(args=args)
        server=SorterNode(); client_node=DummyControl()
        executor=SingleThreadedExecutor();executor.add_node(server);executor.add_node(client_node)
        action=ActionClient(client_node,SortBatch,'/sorter_01/sort_batch')
        statuses=[];feedback=[]
        subscription=client_node.create_subscription(SorterStatus,'/sorter_01/status',lambda msg:statuses.append(msg),10)
        robot=Client('127.0.0.1',server.server.server_address[1])
        frame=0;state=1;ack=done=0;cycles=0;started=0;commands=[];stop_after=3
        def step():
            nonlocal frame,state,ack,done,cycles,started
            now=time.monotonic();frame+=1
            zones={n:'NO_COLOR' for n in 'ABCD'}
            if cycles<stop_after:
                zones['A' if cycles<2 else 'B']='RED' if cycles<2 else 'YELLOW'
            file=root/'camera.json';tmp=root/'camera.tmp'
            tmp.write_text(json.dumps(dict(monotonic=now,timestamp=time.time(),ready=True,camera_session='integration',counter=frame,zone_states=zones)))
            tmp.replace(file)
            command,job,request,active,hb=robot.read()
            if state==1 and request and active and job!=done:
                state=2;ack=job;started=now;commands.append(command)
            elif state==2:
                assert command==commands[-1], 'command mutated while BUSY'
                if not request and now-started>.15:state=3;done=ack;cycles+=1
            elif state==3 and not request and command==0:state=1
            robot.status(state,ack,done)
            executor.spin_once(timeout_sec=.02)
            time.sleep(.01)
        def until(predicate,seconds=12):
            deadline=time.monotonic()+seconds
            while not predicate():
                if time.monotonic()>deadline:raise AssertionError(f'timeout {server.engine.view(time.monotonic())}')
                step()
        def send(task):
            goal=SortBatch.Goal(robot_id='sorter_01',task_id=task,batch_id='batch',timestamp='2026-10-01T00:00:00+00:00')
            future=action.send_goal_async(goal,feedback_callback=lambda f:feedback.append(f.feedback))
            until(future.done)
            return future.result()
        try:
            until(lambda:server.engine.ready(time.monotonic()) and action.server_is_ready())
            assert robot.read()[0]==0
            goal=send('integration_1');assert goal.accepted
            future=goal.get_result_async();until(future.done)
            result=future.result().result
            assert (result.result_code,result.red_count,result.yellow_count)==('SUCCESS',2,1),result
            assert commands==[11,11,22],commands
            assert feedback and any(f.red_count>0 for f in feedback)
            assert any(s.state=='SORTING' and not s.ready for s in statuses)
            duplicate=send('integration_1');assert not duplicate.accepted
            # A new batch can be canceled mid-motion; finish its in-flight cycle first.
            stop_after=4
            until(lambda:server.engine.ready(time.monotonic()) and client_node.ready())
            assert client_node.start('integration_cancel', 'batch')
            assert not client_node.start('must_not_start', 'batch')
            until(lambda:server.engine.phase=='BUSY')
            assert client_node.cancel()
            until(lambda:client_node.last_result is not None)
            result=client_node.last_result
            assert not client_node.busy
            assert client_node.last_feedback is not None
            assert (result.result_code,result.red_count+result.yellow_count)==('CANCELED',1),result
            print('PASS: real ROS Goal/Feedback/Result/Status + TCP BUSY/DONE/READY; A red twice, B yellow, empty SUCCESS 2+1; duplicate rejection; cancel drains 1 cycle')
        finally:
            robot.sock.close();action.destroy();client_node.client.destroy()
            executor.remove_node(server);executor.remove_node(client_node)
            server.close();client_node.destroy_node();executor.shutdown();rclpy.shutdown()


if __name__=='__main__':main()
