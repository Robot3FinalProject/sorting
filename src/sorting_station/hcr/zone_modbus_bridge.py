#!/usr/bin/env python3
"""Serve preview snapshots to HCR; read-only, no START/actuation protocol."""
import argparse
import json
import logging
from pathlib import Path
import struct
import time
from modbus_test_server import Server, receive
import socketserver

DEFAULT_STATE=Path(__file__).resolve().parents[3]/'outputs/sorting_station/hcr_preview/state.json'


def registers(path, now=None):
    now=time.time() if now is None else now
    try:
        data=json.loads(Path(path).read_text())
        age=now-data['timestamp']
        zone,color,counter=data['zone'],data['color'],data['counter']
        if not 0<=age<1 or type(zone) is not int or type(color) is not int or type(counter) is not int:
            return [0]*5
        if not 0<=counter<=65535: return [0]*5
        if data['valid'] is not True or zone not in range(1,5) or color not in (1,2):
            return [0,0,0,0,counter]
        return [zone*10+color,zone,color,1,counter]
    except (OSError,ValueError,KeyError,TypeError):
        return [0]*5


def response(unit,pdu,values):
    fc=pdu[0]
    if unit!=1: return bytes((fc|128,11))
    if fc not in (3,4): return bytes((fc|128,1))
    if len(pdu)!=5: return bytes((fc|128,3))
    address,count=struct.unpack('>HH',pdu[1:])
    if not 1<=count<=125: return bytes((fc|128,3))
    if address+count>len(values): return bytes((fc|128,2))
    return bytes((fc,count*2))+struct.pack('>'+count*'H',*values[address:address+count])


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0]!=self.server.peer: return
        logging.info('HCR connected %s',self.client_address)
        self.request.settimeout(15); last=None
        try:
            while True:
                tx,protocol,length,unit=struct.unpack('>HHHB',receive(self.request,7))
                if protocol or not 2<=length<=254: return
                pdu=receive(self.request,length-1)
                values=registers(self.server.state)
                reply=response(unit,pdu,values)
                self.request.sendall(struct.pack('>HHHB',tx,0,len(reply)+1,unit)+reply)
                marker=(tuple(values[:4]),pdu,reply[0])
                if marker!=last:
                    logging.info('request=%s response=%s preview=%s',pdu.hex(),reply.hex(),values[:4]); last=marker
        except (OSError,EOFError):
            logging.info('HCR disconnected')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,default=DEFAULT_STATE)
    p.add_argument('--host',default='192.168.3.2')
    p.add_argument('--peer',default='192.168.3.100')
    p.add_argument('--port',type=int,default=502)
    args=p.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    try:
        with Server((args.host,args.port),Handler) as server:
            server.state=args.state; server.peer=args.peer
            logging.info('Listening %s:%s; state=%s; preview only; stale after 1s',args.host,args.port,args.state)
            try: server.serve_forever()
            except KeyboardInterrupt: pass
    except OSError as exc:
        p.exit(1,f'{exc}\nStop old test server; verify PC IP and sudo for port 502.\n')


if __name__=='__main__': main()
