#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import shlex
import select
import threading
import subprocess

import socketserver
import ptproxy.socks as socks

REAL_SERVERPORT=55000

def ptproxy(certs, localport, iat=0, ptexec="obfs4proxy -logLevel=ERROR -enableLogging=true"):
    global logtime
    global DEVNULL
    global TRANSPORT_VERSIONS
    global startupinfo
    global CFG
    global PT_PROC
    global PTREADY
    logtime = lambda: time.strftime('%Y-%m-%d %H:%M:%S')
    DEVNULL = open(os.devnull, 'wb')        
    TRANSPORT_VERSIONS = ('1',)
    startupinfo = None
    CFG = {
           "role": "server",
           "state": "/tmp/ptserver",
           # "server": "127.0.0.1:8000",
           "local": "127.0.0.1:" + str(REAL_SERVERPORT),
           "ptexec": ptexec,
           "ptname": "obfs4",
           # "ptargs": "cert=AAAAAAAAAAAAAAAAAAAAAAAAAAAAA+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA;iat-mode=0",
           "ptserveropt": "",
           "ptproxy": ""
    }

    # initialize CFG
    CFG["server"] = "0.0.0.0:" + str(localport)
    CFG["ptargs"] = "cert=" + certs + ";iat-mode=" + str(iat)
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    PT_PROC = None
    PTREADY = threading.Event()

    try:
        CFG['_run'] = True
        if CFG['role'] == 'client':
            ptthr = threading.Thread(target=runpt)
            ptthr.daemon = True
            ptthr.start()
            PTREADY.wait()
            host, port = CFG['local'].split(':')
            server = ThreadedTCPServer(
                (host, int(port)), ThreadedTCPRequestHandler)
            server.serve_forever()
        else:
            runpt()
    finally:
        CFG['_run'] = False
        if PT_PROC:
            PT_PROC.kill()


class PTConnectFailed(Exception):
    pass

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        ptsock = socks.socksocket()
        ptsock.set_proxy(*CFG['_ptcli'])
        host, port = CFG['server'].rsplit(':', 1)
        try:
            ptsock.connect((host, int(port)))
        except socks.GeneralProxyError as ex:
            print(logtime(), ex)
            print(logtime(), 'WARNING: Please check the config and the log of PT.')
        run = 1
        while run:
            rl, wl, xl = select.select([self.request, ptsock], [], [], 300)
            if not rl:
                break
            run = 0
            for s in rl:
                try:
                    data = s.recv(1024)
                except Exception as ex:
                    print(logtime(), ex)
                    continue
                if data:
                    run += 1
                else:
                    continue
                if s is self.request:
                    ptsock.sendall(data)
                elif s is ptsock:
                    self.request.sendall(data)


def ptenv():

    env = os.environ.copy()
    env['TOR_PT_STATE_LOCATION'] = CFG['state']
    env['TOR_PT_MANAGED_TRANSPORT_VER'] = ','.join(TRANSPORT_VERSIONS)
    if CFG["role"] == "client":
        env['TOR_PT_CLIENT_TRANSPORTS'] = CFG['ptname']
        if CFG.get('ptproxy'):
            env['TOR_PT_PROXY'] = CFG['ptproxy']
    elif CFG["role"] == "server":
        env['TOR_PT_SERVER_TRANSPORTS'] = CFG['ptname']
        env['TOR_PT_SERVER_BINDADDR'] = '%s-%s' % (
            CFG['ptname'], CFG['server'])
        env['TOR_PT_ORPORT'] = CFG['local']
        env['TOR_PT_EXTENDED_SERVER_PORT'] = ''
        if CFG.get('ptserveropt'):
            env['TOR_PT_SERVER_TRANSPORT_OPTIONS'] = ';'.join(
                '%s:%s' % (CFG['ptname'], kv) for kv in CFG['ptserveropt'].split(';'))
    else:
        raise ValueError('"role" must be either "server" or "client"')
    return env


def checkproc():
    global PT_PROC
    if PT_PROC is None or PT_PROC.poll() is not None:
        PT_PROC = subprocess.Popen(shlex.split(
            CFG['ptexec']), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=DEVNULL, env=ptenv(), startupinfo=startupinfo)
    return PT_PROC


def parseptline(iterable):
    for ln in iterable:
        ln = ln.decode('utf_8', errors='replace').rstrip('\n')
        sp = ln.split(' ', 1)
        kw = sp[0]
        if kw in ('ENV-ERROR', 'VERSION-ERROR', 'PROXY-ERROR',
                  'CMETHOD-ERROR', 'SMETHOD-ERROR'):
            raise PTConnectFailed(ln)
        elif kw == 'VERSION':
            if sp[1] not in TRANSPORT_VERSIONS:
                raise PTConnectFailed('PT returned invalid version: ' + sp[1])
        elif kw == 'PROXY':
            if sp[1] != 'DONE':
                raise PTConnectFailed('PT returned invalid info: ' + ln)
        elif kw == 'CMETHOD':
            vals = sp[1].split(' ')
            if vals[0] == CFG['ptname']:
                host, port = vals[2].split(':')
                CFG['_ptcli'] = (
                    socks.PROXY_TYPES[vals[1].upper()], host, int(port),
                    True, CFG['ptargs'][:255], CFG['ptargs'][255:] or '\0')
        elif kw == 'SMETHOD':
            vals = sp[1].split(' ')
            if vals[0] == CFG['ptname']:
                print('===== Server information =====')
                print('"server": "%s",' % vals[1])
                print('"ptname": "%s",' % vals[0])
                for opt in vals[2:]:
                    if opt.startswith('ARGS:'):
                        print('"ptargs": "%s",' % opt[5:].replace(',', ';'))
                print('==============================')
        elif kw in ('CMETHODS', 'SMETHODS') and sp[1] == 'DONE':
            print(logtime(), 'PT started successfully.')
            return
        else:
            # Some PTs may print extra debugging info
            print(logtime(), ln)


def runpt():
    global CFG, PTREADY
    while CFG['_run']:
        print(logtime(), 'Starting PT...')
        proc = checkproc()
        # If error then die
        parseptline(proc.stdout)
        PTREADY.set()
        # Use this to block
        # stdout may be a channel for logging
        try:
            out = proc.stdout.readline()
            while out:
                print(logtime(), out.decode('utf_8', errors='replace').rstrip('\n'))
        except Exception:  # original = BrokenPipeError
            pass
        PTREADY.clear()
        #TODO: need to make sure PTREADY is waiting when the entire program is closing
        print(logtime(), 'PT died.')
