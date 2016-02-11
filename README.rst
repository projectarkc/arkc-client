ArkC-Client V0.2
================

ArkC is a lightweight proxy designed to be proof to IP blocking measures
and offer high proxy speed via multi-connection transmission and
swapping connections.

ArkC-Client is the client-side utility. In a LAN environment, it either
works with UPnP-enabled routers or requires NAT configuration if the
client is behind a router.

Setup and Requirement
---------------------

For Windows users, please use our Windows executable in release page.

For users with python3 pip development environment (Note: We don't
recommend using python 2):

::

    sudo pip3 install arkcclient

To install python3 and pip3 with python.h:

Debian/Ubuntu users

::

    sudo apt-get install python3 python3-pip python3-dev

Fedora users

::

    yum install python3 python3-devel python3-pip

You may also install ArkC via source.

To get ArkC Client work, you must satisfy ONE OF the following
conditions (unless you are the expert): 1) connect to public Internet
directly 2) connect to the Internet via a UPnP-enabled router, in a
single-layer LAN 3) router(s) on your route to the public Internet are
properly configured with NAT to allow your server to connect to your
client's "remote\_port" directly

Usage
-----

Run

::

    arkcclient [-h] [-v|-vv] [-pn] -c <Path of the config Json file>

[-pn] is used to disable UPnP.

In this version, any private certificate should be in the form of PEM
without encryption, while any public certificate should be in the form
of ssh-rsa. Generate a key pair with ssh-keygen on GNU/Linux.

For the configuration file, you can find an example here:

::

    {
        "local_cert":"client.pem",
        "remote_cert":"server.pub",
        "local_cert_pub":"client.pub",
        "control_domain":"testing.arkc.org",
        "dns_servers": [
                ["8.8.8.8", 53],
                ["127.0.0.1", 9000]
             ]
    }

NOTE: NO COMMENTS ARE ALLOWED IN JSON FORMAT.

For a full list of settings:

+--------------------+---------------------------------------------------+----------------------------------+
| Index name         | Value Type & Description                          | Required / Default               |
+====================+===================================================+==================================+
| local\_host        | str, proxy listening addr                         | "127.0.0.1"                      |
+--------------------+---------------------------------------------------+----------------------------------+
| local\_port        | integer, proxy port                               | 8001                             |
+--------------------+---------------------------------------------------+----------------------------------+
| remote\_host       | str, listening host                               | "0.0.0.0"                        |
+--------------------+---------------------------------------------------+----------------------------------+
| remote\_port       | integer, listening port                           | random between 20000 and 60000   |
+--------------------+---------------------------------------------------+----------------------------------+
| number             | integer, how many conn. (max. 100)                | 3                                |
+--------------------+---------------------------------------------------+----------------------------------+
| local\_cert        | str, path of client pri                           | REQUIRED                         |
+--------------------+---------------------------------------------------+----------------------------------+
| local\_cert\_pub   | str, path of client pub                           | REQUIRED                         |
+--------------------+---------------------------------------------------+----------------------------------+
| remote\_cert       | str, path of server pub                           | REQUIRED                         |
+--------------------+---------------------------------------------------+----------------------------------+
| control\_domain    | str, standard domain                              | REQUIRED                         |
+--------------------+---------------------------------------------------+----------------------------------+
| dns\_server        | list, servers to send dns query to                | [] (use system resolver)         |
+--------------------+---------------------------------------------------+----------------------------------+
| debug\_ip          | str, address of the client (only for debug use)   | None                             |
+--------------------+---------------------------------------------------+----------------------------------+
| pt\_exec           | str, command line of PT executable                | "obfs4proxy"                     |
+--------------------+---------------------------------------------------+----------------------------------+
| obfs\_level        | integer, obfs leve 0~3, the same as server side   | 0                                |
+--------------------+---------------------------------------------------+----------------------------------+

Note: if obfs\_level is set, pt\_exec must be appropriate set. It is set
to use obfs4 or MEEK, both Tor pluggable transport (abbr: PT). MEEK is
like GoAgent, and obfs4 is used to obfuscate all the traffic.

If set to 1 or 2, Obfs4 will use an IAT mode of (obfs\_level + 1), which
means if obfs\_level is set to 1 or 2, the connection speed may be
affected.

If obfs\_level is set to 3, MEEK will be used to transmit all data via a
pre-configured MEEK service at the server side. By default it passes
through Google App Engine.

Build on Windows
----------------

::

    pip install pyinstaller
    pyinstaller [--onefile] main.py

Acknowledgements
----------------

The client-end software adapted part of the pyotp library created by
Mark Percival m@mdp.im. His code is reused under Python Port copyright,
license attached.

File ptclient.py and meekclient.py is based on ptproxy by Dingyuan Wang.
Code reused and edited under MIT license, attached in file.

License
-------

Copyright 2015 ArkC Technology.

The ArkC-client and ArkC-server utilities are licensed under GNU GPLv2.
You should obtain a copy of the license with the software.

ArkC is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free
Software Foundation, either version 2 of the License, or (at your
option) any later version.

ArkC is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along
with ArkC. If not, see http://www.gnu.org/licenses/.
