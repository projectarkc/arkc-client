#ArkC-client

ArkC is a lightweight proxy based on Python 3 and PyCrypto. It is designed to be proof to IP blocking measures.

ArkC-Client is the client-side utility. It may require NAT configuration if the client is behind a router.

##Setup and Requirement

Running ArkC-Client requires Python 3 and PyCrypto.

For Debian or Ubuntu users:
    
```
sudo apt-get install python3 python3-pip python3-dev python3-psutil obfs4proxy
sudo pip3 install -r requirements.txt
```

NAT configuration may be necessary to make the client receives requests from the server, so that a connection may start.

##Usage

Run 

```
python3 main.py [-h] [-v|-vv] -c <Path of the config Json file, default = config.json>
```

In this version, any private certificate should be in the form of PEM without encryption, while any public certificate should be in the form of ssh-rsa. Note that ssh-rsa files should not include extra blank lines because they are used for hash.

For the configuration file, you can find an example here:

```
{
    "remote_control_host":"example.com",
    "local_cert":"client.pem",
    "remote_cert":"server.pub",
    "local_cert_pub":"client.pub",
    "control_domain":"testing.arkc.org",
    "dns_servers": [
            ["8.8.8.8", 53],
            ["127.0.0.1", 9000]
        ],
    "obfs_level":0
}
```

For a full list of settings:

| Index name            | Value Type & Description | Required / Default|
| ----------------------|:------------------------:| -----------------:|
| local_host            | str, proxy listening addr| "127.0.0.1"       |
| local_port            | integer, proxy port      | 8001              |
| remote_host           | str, listening host      | "0.0.0.0"         |
| remote_port           | integer, listening port  | 8000              |
| number                | integer, how many conn. (max. 100)  | 3                 |
| local_cert            | str, path of client pri  | REQUIRED          |
| local_cert_pub        | str, path of client pub  | REQUIRED          |
| remote_cert           | str, path of server pub  | REQUIRED          |
| control_domain	| str, standard domain     | REQUIRED 	       |
| dns_server            | list, servers to send dns query to | [] (use system resolver)|
| debug_ip              | str, address of the client (only for debug use) | None |
| pt_exec		| str, command line of PT executable | "obfs4proxy" |
| obfs_level		| integer, obfs leve 0~3, the same as server side | 0 |

Note: if obfs_level is set, pt_exec must be appropriate set. It is set to use obfs4 or MEEK, both Tor pluggable transport (abbr: PT). MEEK is like GoAgent, and obfs4 is used to obfuscate all the traffic.

If set to 1 or 2, Obfs4 will use an IAT mode of (obfs_level + 1), which means if obfs_level is set to 1 or 2, the connection speed may be affected.

If obfs_level is set to 3, MEEK will be used to transmit all data via a pre-configured MEEK service at the server side. By default it passes through Google App Engine.

##Build on Windows
```
pip install pyinstaller
pyinstaller [--onefile] main.py
```

##Acknowledgements

The client-end software adapted part of the pyotp library created by Mark Percival <m@mdp.im>. His code is reused under Python Port copyright, license attached.

File ptclient.py and meekclient.py is based on ptproxy by Dingyuan Wang. Code reused and edited under MIT license, attached in file.

##License

Copyright 2015 ArkC Technology.

The ArkC-client and ArkC-server utilities are licensed under GNU GPLv2. You should obtain a copy of the license with the software.

ArkC is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

ArkC is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ArkC.  If not, see <http://www.gnu.org/licenses/>.

