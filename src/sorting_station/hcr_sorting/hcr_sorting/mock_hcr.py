"""Explicit test client, models handshake only. Never connects to a robot."""
import argparse
import socket
import struct
import time
from .modbus import receive


class Client:
    def __init__(self,host,port):
        self.sock=socket.create_connection((host,port),timeout=2)
        self.tx=0

    def exchange(self,pdu):
        self.tx=(self.tx+1)%65536
        self.sock.sendall(struct.pack('>HHHB',self.tx,0,len(pdu)+1,1)+pdu)
        tx,proto,length,unit=struct.unpack('>HHHB',receive(self.sock,7))
        reply=receive(self.sock,length-1)
        if (tx,proto,unit)!=(self.tx,0,1) or reply[0]&128: raise RuntimeError(reply.hex())
        return reply

    def read(self):
        return struct.unpack('>5H',self.exchange(struct.pack('>BHH',3,0,5))[2:])

    def status(self,state,ack,done,error=0):
        self.exchange(struct.pack('>BHHB4H',16,100,4,8,state,ack,done,error))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=1502)
    p.add_argument('--cycle-seconds',type=float,default=2.0)
    args=p.parse_args()
    client=Client(args.host,args.port)
    state=1; ack=done=0; started=0; heartbeat=None; seen=time.monotonic()
    print('MOCK HCR: simulated cycles, no physical motions',flush=True)
    try:
        while True:
            cmd,job,request,active,hb=client.read(); now=time.monotonic()
            if hb!=heartbeat: heartbeat=hb;seen=now
            if now-seen>3: raise RuntimeError('PC heartbeat stopped')
            if state==1 and active and request and job!=done and cmd in (11,12,21,22,31,32,41,42):
                state=2;ack=job;started=now;print(f'BUSY job={job} command={cmd}',flush=True)
            elif state==2 and not request and now-started>=args.cycle_seconds:
                state=3;done=ack;print(f'DONE job={done}',flush=True)
            elif state==3 and cmd==0 and request==0: state=1
            client.status(state,ack,done); time.sleep(.1)
    except KeyboardInterrupt: pass
    finally: client.sock.close()


if __name__=='__main__': main()
