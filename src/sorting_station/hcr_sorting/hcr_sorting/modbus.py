"""Bounded Modbus TCP subset: FC03/04 read; FC06/16 HCR status write."""
from collections import deque
import logging
import socketserver
import struct
import threading
import time


class RegisterBank:
    def __init__(self):
        self.lock=threading.Lock()
        self.pc=[0]*5; self.robot=[0]*4
        self.events=deque(); self.overflow=False

    def update(self, values):
        with self.lock: self.pc=list(values)

    def drain(self):
        with self.lock:
            events=list(self.events); self.events.clear()
            overflow=self.overflow; self.overflow=False
            return events,overflow

    def transact(self, unit, pdu):
        with self.lock: return self._transact(unit,pdu)

    def _transact(self,unit,pdu):
        fc=pdu[0]
        def fail(code): return bytes((fc|128,code))
        if unit!=1: return fail(11)
        if fc in (3,4):
            if len(pdu)!=5: return fail(3)
            start,count=struct.unpack('>HH',pdu[1:])
            if not 1<=count<=125: return fail(3)
            if start+count<=5: values=self.pc[start:start+count]
            elif 100<=start and start+count<=104: values=self.robot[start-100:start-100+count]
            else: return fail(2)
            return bytes((fc,count*2))+struct.pack('>'+count*'H',*values)
        if fc==6:
            if len(pdu)!=5: return fail(3)
            start,value=struct.unpack('>HH',pdu[1:]); values=[value]
            answer=pdu
        elif fc==16:
            if len(pdu)<6: return fail(3)
            start,count,size=struct.unpack('>HHB',pdu[1:6])
            if not 1<=count<=123 or size!=2*count or len(pdu)!=6+size: return fail(3)
            values=list(struct.unpack('>'+count*'H',pdu[6:])); answer=struct.pack('>BHH',fc,start,count)
        else: return fail(1)
        if start<100 or start+len(values)>104: return fail(2)
        candidate=list(self.robot)
        candidate[start-100:start-100+len(values)]=values
        if candidate[0]>4: return fail(3)
        self.robot=candidate
        # State register is the commit marker. Repeated writes are the heartbeat.
        if start==100:
            if len(self.events)>=256:
                self.overflow=True
            else: self.events.append((time.monotonic(),*candidate))
        return answer


def receive(sock,size):
    data=bytearray()
    while len(data)<size:
        chunk=sock.recv(size-len(data))
        if not chunk: raise EOFError
        data.extend(chunk)
    return bytes(data)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        try:
            while True:
                tx,protocol,length,unit=struct.unpack('>HHHB',receive(self.request,7))
                if protocol!=0 or not 2<=length<=254: return
                pdu=receive(self.request,length-1)
                reply=self.server.bank.transact(unit,pdu)
                self.request.sendall(struct.pack('>HHHB',tx,0,len(reply)+1,unit)+reply)
        except (OSError,EOFError): pass


class ModbusServer(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True

    def __init__(self,address,bank,peer):
        self.bank=bank; self.peer=peer
        self.slots=threading.BoundedSemaphore(8)
        super().__init__(address,Handler)

    def verify_request(self,request,client_address):
        return client_address[0]==self.peer

    def process_request(self,request,client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request); return
        try: super().process_request(request,client_address)
        except Exception:
            self.slots.release(); raise

    def process_request_thread(self,request,client_address):
        try: super().process_request_thread(request,client_address)
        finally: self.slots.release()
