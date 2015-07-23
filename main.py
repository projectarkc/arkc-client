#! /usr/bin/env python3

import asyncore
import argparse
from hashlib import sha1

try:
    from Crypto.PublicKey import RSA
except Exception as e:
    print("Library Crypto (pycrypto) is not installed. Fatal error.")
    quit()
#TODO:Need to switch to PKCS for better security

from coordinator import coordinate
from server import servercontrol
from client import clientcontrol

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_LOCAL_PORT = 8001

DEFAULT_REMOTE_PORT = 8000

DEFAULT_LOCAL_CONTROL_PORT = 8002
DEFAULT_REMOTE_CONTROL_PORT = 9000

DEFAULT_REQUIRED = 10

class certloader:
    
    def __init__(self, certfile):
        self.certfile = certfile
    #need to support more formats
    def importKey(self):
        try:
            data = self.certfile.read()
            return RSA.importKey(data)
        except Exception as err:
            print ("Fatal error while loading certificate.")
            print (err)
            quit()
    def getSHA1(self):
        try:
            data = self.certfile.read()
            #TODO: should use compatible SHA1 value
            return sha1(data.encode("UTF-8")).hexdigest()
        except Exception as err:
            print ("Cannot get SHA1 of the certificate.")
            print (err)
            quit()
                

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ArkC Client")
    try:
        #TODO: Help files
        parser.add_argument('-lh', '--local-host', dest="local_host", default=DEFAULT_LOCAL_HOST)
        parser.add_argument('-lp', '--local-port',  dest="local_port", type=int, default=DEFAULT_LOCAL_PORT)
        parser.add_argument('-rh', '--remote-host',  dest="remote_host", default=DEFAULT_LOCAL_HOST)
        parser.add_argument('-rp', '--remote-port',  dest="remote_port", type=int, default=DEFAULT_REMOTE_PORT)
        parser.add_argument('-rch', '--remote-control-host',  dest="remote_control_host", help="You must specify a remote control host to activate.", required = True)
        parser.add_argument('-rcp', '--remote-control-port',  dest="remote_control_port", type=int, default=DEFAULT_REMOTE_CONTROL_PORT)
        parser.add_argument('-lcp', '--local-control-port', dest="local_control_port", type=int, default=DEFAULT_LOCAL_CONTROL_PORT)
        parser.add_argument('-rc', '--remote-cert',  dest="remote_cert", help = "Remote host public key (must be specified)", required = True)
        parser.add_argument('-lc', '--local-cert',  dest="local_cert", help = "Local host key (must be specified)", required = True)
        parser.add_argument('--local-cert-public',  dest="local_cert_pub", help = "Local host public key for SHA1 (must be specified)", required = True)
        parser.add_argument('-n', '--number',  dest="number", type=int, default=DEFAULT_REQUIRED)
        options = parser.parse_args()
        try:
            remote_cert_file = open(options.remote_cert, "r")            
            remotecert = certloader(remote_cert_file).importKey()
            remote_cert_file.close()
        except Exception as err:
            print ("Fatal error while loading remote host certificate.")
            print (err)
            quit()
            
        try:
            local_cert_file = open(options.local_cert, "r")
            localcert = certloader(local_cert_file).importKey()
            local_cert_file.close()
            if not localcert.has_private():
                print("Fatal error, no private key included in local certificate.")
        except Exception as err:
            print ("Fatal error while loading local certificate.")
            print (err)
            quit()
            
        try:
            local_pub_file = open(options.local_cert_pub, "r")
            localpub = certloader(local_pub_file).getSHA1()
            local_pub_file.close()
        except Exception as err:
            print ("Fatal error while calculating SHA1 digest.")
            print (err)
            quit()
            
    except Exception as e:
        print (e)
    
    try:
        clientcontrol(
            servercontrol(
                options.remote_host,
                options.remote_port,
                coordinate(
                    options.remote_control_host,
                    options.remote_control_port,
                    options.local_control_port,
                    localcert,
                    remotecert,
                    localpub,
                    options.number
                    )
                ),
            options.local_host,
            options.local_port
            )
    except Exception as e:
        print (e)
    asyncore.loop()
