#! /usr/bin/env python3

import asyncore
import optparse

from Crypto.PublicKey import RSA

from coordinator import coordinate
from server import servercontrol
from client import clientcontrol

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_LOCAL_PORT = 8001

DEFAULT_REMOTE_PORT = 8000

DEFAULT_LOCAL_CONTROL_PORT = 8002
DEFAULT_REMOTE_CONTROL_PORT = 9000

if __name__ == '__main__':
    parser = optparse.OptionParser()
    try:
        parser.add_option('--local-host', dest="local_host", default=DEFAULT_LOCAL_HOST)
        parser.add_option('--local-port',  dest="local_port", type='int', default=DEFAULT_LOCAL_PORT)
        parser.add_option('--remote-host',  dest="remote_host", default = "")
        parser.add_option('--remote-port',  dest="remote_port", type='int', default=DEFAULT_REMOTE_PORT)
        parser.add_option('--remote-control-host',  dest="remote_control_host", default="0.0.0.0")
        parser.add_option('--remote-control-port',  dest="remote_control_port", type='int', default=DEFAULT_REMOTE_CONTROL_PORT)
        parser.add_option('--local-control-port', dest="local_control_port", type='int', default=DEFAULT_LOCAL_CONTROL_PORT)
        parser.add_option('--remote-cert',  dest="remote_cert", default = "")
        parser.add_option('--local-cert',  dest="local_cert", default = "")
        options, args = parser.parse_args()
        if options.remote_host == "":
            print("Fatal error, remote host not specified.")
            quit()
        if options.remote_cert == "":
            print("Fatal error, remote host certificate not specified.")
            quit()
        if options.local_cert == "":
            print("Fatal error, local certificate not specified.")
            quit()
        try:
            remote_cert_file = open(options.remote_cert, "r")
            cert = RSA.importKey(remote_cert_file.read())
            remotecert = cert.publickey()
            remote_cert_file.close()
        except Exception as err:
            print ("Fatal error while loading remote host certificate.")
            print (err)
            quit()
            
        try:
            local_cert_file = open(options.local_cert, "r")
            localcert = RSA.importKey(remote_cert_file.read())
            local_cert_file.close()
            if not localcert.has_private():
                print("Fatal error, no private key included in local certificate.")
        except IOError as err:
            print ("Fatal error while loading local certificate.")
            print (err)
            quit()
        
        remote_control_host = options.remote_control_host
        if remote_control_host == "0.0.0.0":
            remote_control_host = options.remote_host
    except Exception as e:
        print (e)
    
    try:
        clientcontrol(
            servercontrol(
                options.remote_host,
                options.remote_port,
                coordinate(
                    remote_control_host,
                    options.remote_control_port,
                    options.local_control_port,
                    localcert,
                    remotecert
                    )
                ),
            options.local_host,
            options.local_port
            )
    except Exception as e:
        print (e)
    asyncore.loop()
