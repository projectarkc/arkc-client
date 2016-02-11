#! /usr/bin/env python3

# By ArkC developers
# Released under GNU General Public License 2

import asyncore
import argparse
import logging
import json
import sys

from common import certloader
from coordinator import Coordinate
from server import ServerControl
from client import ClientControl

# Const used in the client.

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_REMOTE_HOST = ''
DEFAULT_LOCAL_PORT = 8001
DEFAULT_REMOTE_PORT = 8000
DEFAULT_REQUIRED = 3
DEFAULT_DNS_SERVERS = [["8.8.8.8", 53]]
DEFAULT_OBFS4_EXECADDR = "obfs4proxy"


def main():
    parser = argparse.ArgumentParser(description=None)
    try:
        # Load arguments
        parser.add_argument(
            "-v", dest="v", action="store_true", help="show detailed logs")
        parser.add_argument(
            "-vv", dest="vv", action="store_true", help="show debug logs")
        parser.add_argument('-c', '--config', dest="config", required=True,
                            help="Specify a configuration files, REQUIRED for ArkC Client to start")
        parser.add_argument('-fs', '--frequent-swap', dest="fs", action="store_true",
                            help="Use frequent connection swapping")
        parser.add_argument('-pn', '--public-addr', dest="pn", action="store_true",
                            help="Disable UPnP when you have public network IP address (or NAT has been manually configured)")

        parser.add_argument("-v6", dest="ipv6", default="",
                            help="Enable this option to use IPv6 address (only use it if you have one)")
        print("""ArkC Client V0.1.2,  by ArkC Technology.
The programs is distributed under GNU General Public License Version 2.
""")

        options = parser.parse_args()

        data = {}

        # Load json configuration file
        try:
            data_file = open(options.config)
            data = json.load(data_file)
            data_file.close()
        except Exception as err:
            logging.fatal(
                "Fatal error while loading configuration file.\n" + err)
            quit()

        if "control_domain" not in data:
            logging.fatal("missing control domain")
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

        if data["number"] > 100:
            data["number"] = 100

        if "dns_servers" not in data:
            data["dns_servers"] = DEFAULT_DNS_SERVERS

        if "pt_exec" not in data:
            data["pt_exec"] = DEFAULT_OBFS4_EXECADDR

        if "debug_ip" not in data:
            data["debug_ip"] = None

        if "obfs_level" not in data:
            data["obfs_level"] = 0

        # Load certificates
        try:
            serverpub_data = open(data["remote_cert"], "r").read()
            serverpub = certloader(serverpub_data).importKey()
        except KeyError as e:
            logging.fatal(
                e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading remote host certificate.")
            print (err)
            quit()

        try:
            clientpri_data = open(data["local_cert"], "r").read()
            clientpri = certloader(clientpri_data).importKey()
            clientpri_sha1 = certloader(clientpri_data).getSHA1()
            if not clientpri.has_private():
                print(
                    "Fatal error, no private key included in local certificate.")
        except KeyError as e:
            logging.fatal(
                e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading local certificate.")
            print (err)
            quit()

        try:
            clientpub_data = open(data["local_cert_pub"], "r").read()
            clientpub_sha1 = certloader(clientpub_data).getSHA1()
        except KeyError as e:
            logging.fatal(
                e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while calculating SHA1 digest.")
            print (err)
            quit()

        # TODO: make it more elegant
        if options.vv:
            logging.basicConfig(
                stream=sys.stdout, level=logging.DEBUG, format="%(levelname)s: %(asctime)s; %(message)s")
        elif options.v:
            logging.basicConfig(
                stream=sys.stdout, level=logging.INFO, format="%(levelname)s: %(asctime)s; %(message)s")
        else:
            logging.basicConfig(
                stream=sys.stdout, level=logging.WARNING, format="%(levelname)s: %(asctime)s; %(message)s")

        if options.fs:
            swapfq = 3
        else:
            swapfq = 8

    except Exception as e:
        print ("An error occurred: \n")
        print(e)

    # Start the main event loop
    try:
        ctl = Coordinate(
            data["control_domain"],
            clientpri,
            clientpri_sha1,
            serverpub,
            clientpub_sha1,
            data["number"],
            data["remote_host"],
            data["remote_port"],
            data["dns_servers"],
            data["debug_ip"],
            swapfq,
            data["pt_exec"],
            data["obfs_level"],
            options.ipv6,
            options.pn
        )
        sctl = ServerControl(
            data["remote_host"],
            data["remote_port"],
            ctl,
            pt=bool(data["obfs_level"])
        )
        cctl = ClientControl(
            ctl,
            data["local_host"],
            data["local_port"]
        )

    except KeyError as e:
        print(e)
        logging.fatal("Bad config file. Quitting.")
        quit()

    except Exception as e:
        print ("An error occurred: \n")
        print(e)

    try:
        asyncore.loop(use_poll=1)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
