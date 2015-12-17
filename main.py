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
DEFAULT_REQUIRED = 3
DEFAULT_DNS_SERVERS = [["8.8.8.8", 53]]
DEFAULT_OBFS4_EXECADDR = "obfs4proxy"

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ArkC Client")
    try:
        # Load arguments
        parser.add_argument("-v", dest="v", action="store_true", help="show detailed logs")
        parser.add_argument('-c', '--config', dest="config", help="You must specify a configuration files. By default ./config.json is used.", default='config.json')
        parser.add_argument('-fs', '--frequent-swap', dest="fs", action="store_true", help="Use frequent connection swapping")  # #TODO: support this function
        options = parser.parse_args()

        data = {}

        # Load json configuration file
        try:
            data_file = open(options.config)
            data = json.load(data_file)
            data_file.close()
        except Exception as err:
            logging.error("Fatal error while loading configuration file.\n" + err)
            quit()

        if "control_domain" not in data:
            logging.error("missing control domain")
            quit()

        # Apply default values
        if "local_host" not in data:
            data["local_host"] = DEFAULT_LOCAL_HOST

        if "local_port" not in data:
            data["local_port"] = DEFAULT_LOCAL_PORT

        if "remote_host" not in data:
            data["remote_host"] = DEFAULT_REMOTE_HOST

        if "remote_port" not in data:
            data["remote_port"] = DEFAULT_REMOTE_PORT

        if "number" not in data:
            data["number"] = DEFAULT_REQUIRED

        if "dns_servers" not in data:
            data["dns_servers"] = DEFAULT_DNS_SERVERS
        
        if "obfs4_exec" not in data:
            data["obfs4_exec"] = DEFAULT_OBFS4_EXECADDR

        if "debug_ip" not in data:
            data["debug_ip"] = None


        # Load certificates
        try:
            remotecert_data = open(data["remote_cert"], "r").read()
            remotecert = certloader(remotecert_data).importKey()
        except KeyError as e:
            logging.error(e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading remote host certificate.")
            print (err)
            quit()

        try:
            localpri_data = open(data["local_cert"], "r").read()
            localpri = certloader(localpri_data).importKey()
            localpri_sha1 = certloader(localpri_data).getSHA1()
            if not localpri.has_private():
                print("Fatal error, no private key included in local certificate.")
        except KeyError as e:
            logging.error(e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading local certificate.")
            print (err)
            quit()

        try:
            localpub_data = open(data["local_cert_pub"], "r").read()
            localpub_sha1 = certloader(localpub_data).getSHA1()
        except KeyError as e:
            logging.error(e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while calculating SHA1 digest.")
            print (err)
            quit()

        if options.v:
            logging.basicConfig(level=logging.INFO)

        if options.fs:
            swapfq = 3
        else:
            swapfq = 8

    except Exception as e:
        print ("An error occurred: \n")
        print(e)

    # Start the main event loop
    try:
        ctl = coordinate(
                    data["control_domain"],
                    localpri,
                    localpri_sha1,
                    remotecert,
                    localpub_sha1,
                    data["number"],
                    data["remote_host"],
                    data["remote_port"],
                    data["dns_servers"],
                    data["debug_ip"],
                    swapfq, 
                    data["obfs4_exec"]
                    )
        sctl = servercontrol(ctl)
        cctl = clientcontrol(
            ctl,
            data["local_host"],
            data["local_port"]
            )

    except KeyError as e:
        print(e)
        logging.error("Bad config file. Quitting.")
        quit()

    #except Exception as e:
    #    print ("An error occurred: \n")
    #    print(e)
    asyncore.loop()
