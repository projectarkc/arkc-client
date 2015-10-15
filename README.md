#ArkC-client

ArkC is a lightweight proxy based on Python 3 and PyCrypto. It is designed to be proof to IP blocking measures.

ArkC-Client is the client-side utility. It may require NAT configuration if the client is behind a router.

##Setup and Requirement

Running ArkC-Client requires Python 3 and PyCrypto.

For Debian or Ubuntu users:
    
    sudo apt-get install python3 python3-pip python3-dev
    sudo pip3 install pycrypto

NAT configuration may be necessary to make the client receives requests from the server, so that a connection may start.

##Usage

Run 

	python3 main.py [-h] [-v] -c <Path of the config Json file, default = config.json>

In this version, any private certificate should be in the form of PEM without encryption, while any public certificate should be in the form of ssh-rsa. Note that ssh-rsa files should not include extra blank lines because they are used for hash.

For the configuration file, you can find an example here:

{
	"control_domain":"example.com",
	"local_cert":"client.pem",
	"remote_cert":"server.pub",
	"local_cert_pub":"client.pub"
}

More details shall be added at a stable release.

##License

Copyright 2015 ArkC contributers

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

