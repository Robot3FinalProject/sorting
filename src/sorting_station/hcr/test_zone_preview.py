import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
import numpy as np
from zone_preview import classify, Stable, select, validate_rois
from zone_modbus_bridge import registers, response, Server, Handler, receive


class Tests(unittest.TestCase):
    def test_realsense_selection(self):
        from realsense_camera import choose_device
        self.assertEqual(choose_device([('RealSense D435','123')]),('RealSense D435','123'))
        self.assertEqual(choose_device([('RealSense D435','123'),('RealSense D435','456')], '456')[1],'456')
        for devices,serial in [([],None),([('Other Camera','123')],None),([('RealSense D435','123')],'456'),([('RealSense D435','123'),('RealSense D435','456')],None)]:
            with self.assertRaises(RuntimeError): choose_device(devices,serial)

    def test_colors(self):
        for bgr,expected in [((0,0,255),'RED'),((0,255,255),'YELLOW'),((80,80,80),'NO_COLOR'),((255,0,0),'NO_COLOR')]:
            self.assertEqual(classify(np.full((30,30,3),bgr,np.uint8))[0],expected)
        img=np.zeros((30,30,3),np.uint8); img[:15]=(0,0,255);img[15:]=(0,255,255)
        self.assertEqual(classify(img)[0],'MIXED')

    def test_priority_and_stability(self):
        self.assertEqual(select({'A':'MIXED','B':'YELLOW','C':'RED'}),(2,2))
        self.assertEqual(select({'B':'YELLOW','C':'RED'},'DCBA'),(3,1))
        self.assertEqual(select({'A':'WAIT'}),(0,0))
        s=Stable(.3)
        self.assertEqual(s.update('RED',0),'WAIT')
        self.assertEqual(s.update('RED',.31),'RED')
        self.assertEqual(s.update('NO_COLOR',.32),'WAIT')
        self.assertEqual(s.update('RED',.33),'WAIT')

    def test_rois(self):
        validate_rois({'A':[0,0,10,10],'B':[10,0,10,10]},20,20)
        for rois in [{'A':[-1,0,10,10]},{'A':[0,0,40,10]},{'A':[0,0,10,10],'B':[5,0,10,10]}]:
            with self.assertRaises(ValueError): validate_rois(rois,20,20)

    def test_staleness(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json'
            p.write_text(json.dumps(dict(timestamp=10,zone=2,color=2,valid=True,counter=7)))
            self.assertEqual(registers(p,10.5),[22,2,2,1,7])
            self.assertEqual(registers(p,11),[0]*5)
            self.assertEqual(registers(p,9),[0]*5)
            p.write_text('{'); self.assertEqual(registers(p),[0]*5)

    def test_tcp(self):
        with tempfile.TemporaryDirectory() as d, Server(('127.0.0.1',0),Handler) as server:
            p=Path(d)/'state.json'
            p.write_text(json.dumps(dict(timestamp=time.time(),zone=4,color=1,valid=True,counter=3)))
            server.state=p;server.peer='127.0.0.1'
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                with socket.create_connection(server.server_address,timeout=2) as sock:
                    for i,(unit,pdu,expected) in enumerate([(1,'0300000001','03020029'),(1,'0400000005','040a00290004000100010003'),(1,'0600000001','8601'),(1,'0300050001','8302'),(2,'0300000001','830b')]):
                        raw=bytes.fromhex(pdu);packet=struct.pack('>HHHB',i,0,len(raw)+1,unit)+raw
                        sock.sendall(packet[:2]);sock.sendall(packet[2:])
                        tx,proto,length,u=struct.unpack('>HHHB',receive(sock,7))
                        self.assertEqual((tx,proto,u),(i,0,unit))
                        self.assertEqual(receive(sock,length-1).hex(),expected)
            finally: server.shutdown();t.join()


if __name__=='__main__': unittest.main()
