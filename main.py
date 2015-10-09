#! /usr/bin/env python3

# By ArkC developers
# Released under GNU General Public License 2

import asyncore
import argparse
import logging
import json

from common import certloader
from coordinator import coordinate
from server import servercontrol
from client import clientcontrol

# Const used in the client.

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_REMOTE_HOST = "0.0.0.0"

DEFAULT_LOCAL_PORT = 8001
DEFAULT_REMOTE_PORT = 8000
#DEFAULT_LOCAL_CONTROL_PORT = 8002
DEFAULT_REMOTE_CONTROL_PORT = 9000

DEFAULT_REQUIRED = 3  # TODO: Edit after using multi-connections              

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ArkC Client")
    try:
        # TODO: Help strings
        # Load arguments
        parser.add_argument("-v", action="store_true", help="show detailed logs")
        #parser.add_argument('-lh', '--local-host', dest="local_host", default=DEFAULT_LOCAL_HOST)
        #parser.add_argument('-lp', '--local-port', dest="local_port", type=int, default=DEFAULT_LOCAL_PORT)
        #parser.add_argument('-rh', '--remote-host', dest="remote_host", default=DEFAULT_REMOTE_HOST)
        #parser.add_argument('-rp', '--remote-port', dest="remote_port", type=int, default=DEFAULT_REMOTE_PORT)
        #parser.add_argument('-rch', '--remote-control-host', dest="remote_control_host", help="You must specify a remote control host to activate.", required=True)
        #parser.add_argument('-rcp', '--remote-control-port', dest="remote_control_port", type=int, default=DEFAULT_REMOTE_CONTROL_PORT)
        #parser.add_argument('-rc', '--remote-cert', dest="remote_cert", help="Remote host public key (must be specified)", required=True)
        #parser.add_argument('-lc', '--local-cert', dest="local_cert", help="Local host key (must be specified)", required=True)
        #parser.add_argument('--local-cert-public', dest="local_cert_pub", help="Local host public key for SHA1 (must be specified)", required=True)
        #parser.add_argument('-n', '--number', dest="number", type=int, default=DEFAULT_REQUIRED)
        parser.add_argument('-c', '--config', dest = "config", help="You must specify a configuration files. By default ./config.json is used.", default = 'config.json')
        options = parser.parse_args()
        
        data = {}
                
        try:
            data_file = open(options.config)    
            data = json.load(data_file)
            data_file.close()
        except Exception as err:
            logging.error("Fatal error while loading configuration file.\n" + err)
            quit()
        
        if "local_host" not in data:
            data["local_host"] = DEFAULT_LOCAL_HOST
            
        if "local_port" not in data:
            data["local_port"] = DEFAULT_LOCAL_PORT
        
        if "remote_host"not in data:
            data["remote_host"] = DEFAULT_REMOTE_HOST
            
        if "remote_port"not in data:
            data["remote_port"] = DEFAULT_REMOTE_PORT
            
        if "remote_control_port"not in data:
            data["remote_control_port"] = DEFAULT_REMOTE_CONTROL_PORT
            
        if "number"not in data:
            data["number"] = DEFAULT_REQUIRED
            
        
        # Load certificates
        try:
            remote_cert_file = open(data["remote_cert"], "r")            
            remotecert = certloader(remote_cert_file).importKey()
            remote_cert_file.close()
        except KeyError as e:
            logging.error(e + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading remote host certificate.")
            print (err)
            quit()
            
        try:
            local_cert_file = open(data["local_cert"], "r")
            localcert = certloader(local_cert_file).importKey()
            local_cert_file.close()
            if not localcert.has_private():
                print("Fatal error, no private key included in local certificate.")
        except KeyError as e:
            logging.error(e + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading local certificate.")
            print (err)
            quit()
            
        try:
            local_pub_file = open(data["local_cert_pub"], "r")
            localpub = certloader(local_pub_file).getSHA1()
            local_pub_file.close()
        except KeyError as e:
            logging.error(e + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while calculating SHA1 digest.")
            print (err)
            quit()
            
        if options.v:
            logging.basicConfig(level=logging.INFO)
            
    except Exception as e:
        print ("An error occurred: \n" + e)
    
    # Start the main event loop
    try:
        ctl = coordinate(
                    data["remote_control_host"],
                    data["remote_control_port"],
                    localcert,
                    remotecert,
                    localpub,
                    data["number"],
                    data["remote_port"]
                    )
        sctl = servercontrol(
                data["remote_host"],
                data["remote_port"],
                ctl
                )
        cctl = clientcontrol(
            ctl,
            data["local_host"],
            data["local_port"]
            )
    
    except KeyError as e:
        logging.error(e + "is not found in the config file. Quitting.")
        quit()
    
    except Exception as e:
        print ("An error occurred: \n" + e)
    asyncore.loop()
