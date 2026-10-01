#!/usr/bin/env python3
"""Diagnostic only: unit 1, address 0 = configurable integer (default 123), FC03/04; no writes or robot control."""
import argparse
import logging
import socket
import socketserver
import struct


def reply(unit, pdu, value=123):
    fc = pdu[0]
    if unit != 1:
        return bytes((fc | 0x80, 11))
    if fc not in (3, 4):
        return bytes((fc | 0x80, 1))
    if len(pdu) != 5:
        return bytes((fc | 0x80, 3))
    address, count = struct.unpack('>HH', pdu[1:])
    if not 1 <= count <= 125:
        return bytes((fc | 0x80, 3))
    if address != 0 or count != 1:
        return bytes((fc | 0x80, 2))
    return bytes((fc, 2)) + struct.pack('>H', value)


def receive(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    return bytes(data)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0] != self.server.allowed_peer:
            logging.warning('Rejected peer %s', self.client_address)
            return
        logging.info('Connected: %s', self.client_address)
        self.request.settimeout(15)
        count = 0
        try:
            while True:
                header = receive(self.request, 7)
                transaction, protocol, length, unit = struct.unpack('>HHHB', header)
                if protocol != 0 or not 2 <= length <= 254:
                    logging.warning('Invalid MBAP header; disconnecting')
                    return
                pdu = receive(self.request, length - 1)
                response = reply(unit, pdu, self.server.value)
                self.request.sendall(struct.pack('>HHHB', transaction, 0, len(response) + 1, unit) + response)
                count += 1
                if count == 1 or count % 100 == 0:
                    logging.info('requests=%d unit=%d request=%s response=%s %s',
                                 count, unit, pdu.hex(), response.hex(),
                                 f'READ OK: value={self.server.value}' if response[0] < 128 else 'EXCEPTION (check unit/type/address/quantity)')
        except (EOFError, OSError):
            logging.info('Disconnected: %s', self.client_address)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='192.168.3.2')
    parser.add_argument('--port', type=int, default=502)
    parser.add_argument('--peer', default='192.168.3.100')
    parser.add_argument('--value', type=int, default=123, help='Test integer (0..65535)')
    args = parser.parse_args()
    if not 0 <= args.value <= 65535:
        parser.error('--value must be 0..65535')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    try:
        with Server((args.host, args.port), Handler) as server:
            server.allowed_peer = args.peer
            server.value = args.value
            logging.info('Listening %s:%d; peer=%s; unit=1; address=0; value=%d; read-only; Ctrl+C to stop', args.host, args.port, args.peer, args.value)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                logging.info('Stopped')
    except OSError as exc:
        parser.exit(1, f'Cannot listen: {exc}\nPort 502 requires sudo; host IP must exist.\n')


if __name__ == '__main__':
    main()
