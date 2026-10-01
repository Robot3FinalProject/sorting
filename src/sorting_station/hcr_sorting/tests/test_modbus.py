import socket
import struct
import threading
import unittest
from hcr_sorting.modbus import RegisterBank, ModbusServer, receive


class ModbusTests(unittest.TestCase):
    def test_commit_order_and_protection(self):
        b=RegisterBank();b.update([11,5,1,1,3])
        self.assertEqual(b.transact(1,bytes.fromhex('0600000001')),bytes.fromhex('8602'))
        b.transact(1,struct.pack('>BHH',6,101,5))
        self.assertEqual(b.drain()[0],[])
        b.transact(1,struct.pack('>BHH',6,100,2))
        self.assertEqual(b.drain()[0][0][1:],(2,5,0,0))
        self.assertEqual(b.transact(1,bytes.fromhex('0300000001')),bytes.fromhex('0302000b'))
        self.assertEqual(b.transact(1,bytes.fromhex('10006400020400010002')),bytes.fromhex('1000640002'))

    def test_errors(self):
        b=RegisterBank()
        for request,expected in [('100064000208','9003'),('0600640009','8603'),('0300040002','8302'),('0300000000','8303'),('050064ff00','8501')]:
            self.assertEqual(b.transact(1,bytes.fromhex(request)).hex(),expected)
        self.assertEqual(b.transact(2,bytes.fromhex('0300000001')).hex(),'830b')

    def test_tcp_fragmented_and_pipelined(self):
        bank=RegisterBank()
        with ModbusServer(('127.0.0.1',0),bank,'127.0.0.1') as server:
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                with socket.create_connection(server.server_address,timeout=2) as s:
                    pdu=struct.pack('>BHHB4H',16,100,4,8,2,7,0,0)
                    packet=struct.pack('>HHHB',1,0,len(pdu)+1,1)+pdu
                    s.sendall(packet[:3]);s.sendall(packet[3:]+bytes.fromhex('000200000006010300640004'))
                    for tx in [1,2]:
                        header=struct.unpack('>HHHB',receive(s,7));self.assertEqual(header[0],tx)
                        reply=receive(s,header[2]-1);self.assertFalse(reply[0]&128)
                    self.assertEqual(bank.drain()[0][0][1:],(2,7,0,0))
            finally:server.shutdown();t.join()


if __name__=='__main__':unittest.main()
