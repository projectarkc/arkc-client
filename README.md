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

```
{
    "control_domain":"example.com",
    "local_cert":"client.pem",
    "remote_cert":"server.pub",
    "local_cert_pub":"client.pub"
}
```

For a full list of settings:

| Index name            | Value Type & Description | Required / Default|
| ----------------------|:------------------------:| -----------------:|
| remote_control_host   | str, UDP dest. host      | REQUIRED          |
| remote_control_port   | integer, UDP dest. port  | 9000              |
| local_host            | str, proxy listening addr| "127.0.0.1"       |
| local_port            | integer, proxy port      | 8001              |
| remote_host           | str, listening host      | "0.0.0.0"         |
| remote_port           | integer, listening port  | 8000              |
| number                | integer, how many conn.  | 3                 |
| local_cert            | str, path of client pri  | REQUIRED          |
| local_cert_pub        | str, path of client pub  | REQUIRED          |
| remote_cert           | str, path of server pub  | REQUIRED          |

##License

Copyright 2015 ArkC contributers

The ArkC-client and ArkC-server utilities are licensed under GNU GPLv2. You should obtain a copy of the license with the software.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.

