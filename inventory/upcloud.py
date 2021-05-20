#!/usr/bin/env python

"""
UpCloud external inventory script
======================================

Generates Ansible inventory of UpCloud servers.
The script implements --list and --host required by Ansible.

UpCloud's API credentials may be placed in upcloud.ini or into environment variables
UPCLOUD_API_USER and UPCLOUD_API_PASSWD.

---

The --list argument may also be called: --list --return-ip-addresses to return IP-addresses instead of hostnames.
UpCloud does not enforce that hostnames are actually reachable over SSH or unique, so this option might be useful.

The groups created by --list match UpCloud's Tags and zones. 'uc_all' group contains all hosts from UpCloud.

---

When run against a specific host with --host, the script returns a JSON object witch uc_ namespaced keys.
The response's keys are described at https://www.upcloud.com/api/7-servers/#get-server-details.

Note: --host does not work with IP-addresses without --return-ip-addresses. If this flag is set in .ini,
both --list and --host work with IP-addresses.

An example response for reference:

```
{
    'uc_firewall': 'off',
    'uc_ip_addresses': [
        {'access': 'private', 'family': 'IPv4', 'address': ''},
        {'access': 'public',  'family': 'IPv6', 'address': ''},
        {'access': 'public',  'family': 'IPv4', 'address': ''}
    ],
    'uc_core_number': '1',
    'uc_memory_amount': '1024',
    'uc_timezone': 'UTC',
    'uc_storage_devices': [
        {
            'storage_title': 'First device',
            'type': 'disk',
            'storage': '01db8471-3a4d-41f2-b514-0bf1eeeb7c07',
            'storage_size': 30,
            'address': 'virtio:0'
        }
    ],
    'uc_uuid': '007171ef-f525-4580-822c-b9f440ce650c',
    'uc_zone': 'de-fra1',
    'uc_title': 'web1',
    'uc_hostname': 'web1.example.com',
    'uc_state': 'started',
    'uc_vnc_password': '',
    'uc_vnc': 'off',
    'uc_boot_order': 'cdrom,disk',
    'uc_host': 6614172291,
    'uc_plan': '1xCPU-1GB',
    'uc_tags': ['webservers'],
    'uc_video_model': 'cirrus',
    'uc_license': 0,
    'uc_nic_model': 'virtio'
}
```
"""

import os
import sys
import argparse
from six.moves import configparser


try:
    import upcloud_api
except ImportError as e:
    print(e)
    # no need to test for version number as pre 0.3.0 package was named differently
    err_msg = "failed=True msg='UpCloud's Python API client (v. 0.3.0 or higher) is required for this script. (`pip install upcloud-api`)'"
    sys.stderr.write(err_msg)
    sys.exit(-1)

try:
    import json
except ImportError:
    import simplejson as json


def get_hostname_or_ip(server, get_ip_address, get_non_fqdn_name, addr_family):
    """Returns a server's hostname. If get_ip_address==True, returns its public IP-address."""
    if get_ip_address:
        # prevent API request during get_public_ip, as IPs were matched manually
        # bypass server.__setattr__ as setting populated is not normallow allowed by the class
        object.__setattr__(server, "populated", True)
        public_ip_addresses = [server.get_public_ip(addr_family=addr_family)]
        if len(public_ip_addresses) == 0:
            public_ip_addresses = [server.get_public_ip()]
        return public_ip_addresses

    hostname = server.hostname.split(".")[0]
    if get_non_fqdn_name and hostname != server.hostname:
        return [server.hostname, server.hostname.split(".")[0]]
    return [server.hostname]


def assign_ips_to_servers(manager, servers):
    """
    Queries all IP-addresses from UpCloud and matches them with servers.
    This is an optimisation; we manually populate IP-addresses to the server objects
    so server.get_public_ip() does not have to perform an API GET request
    (this would otherwise lead to a request per every server).
    """

    # build a dict for fast search
    servermap = dict()
    for server in servers:
        servermap[server.uuid] = server

        # bypass server.__setattr__ as it does not normally allow assigning ip_addresses manually
        object.__setattr__(server, "ip_addresses", [])

    # assign IPs to their corresponding server
    ips = manager.get_ips(ignore_ips_without_server=True)
    for ip in ips:
        servermap[ip.server].ip_addresses.append(ip)


def list_servers(manager, get_ip_address, return_non_fqdn_names, default_ipv_version):
    """Lists all servers' hostnames. If get_ip_address==True, lists IP-addresses."""
    servers = manager.get_servers()

    if get_ip_address:
        assign_ips_to_servers(manager, servers)

    groups = dict()
    groups["uc_all"] = []
    for server in servers:
        if server.state == "started":
            for hostname_or_ip in get_hostname_or_ip(
                server, get_ip_address, return_non_fqdn_names, default_ipv_version
            ):
                groups["uc_all"].append(hostname_or_ip)

            # group by tags
            for tag in server.tags:
                if tag not in groups:
                    groups[tag] = []
                groups[tag].append(hostname_or_ip)

            # group by zones
            formatted_zone = server.zone.replace("-", "_")
            if formatted_zone not in groups:
                groups[formatted_zone] = []
            groups[formatted_zone].append(hostname_or_ip)

    print(json.dumps(groups))
    return groups


def get_server(manager, search_item, with_ip_addresses, return_non_fqdn_names=False):
    """
    Handles --host.

    Search_item can be a) hostname b) uuid c) ip_addresses.
    c) is only checked if with_ip_addresses==True.
    """

    def namespace_fields(server):
        """Generate a JSON response to a --host call"""
        namespaced_server_dict = {}
        for key, value in server.to_dict().items():
            namespaced_server_dict["uc_" + key] = value
        return namespaced_server_dict

    if with_ip_addresses:
        ips = manager.get_ips()
        for ip in ips:
            if ip.address == search_item:
                server = manager.get_server(ip.server)
                server_dict = namespace_fields(server)
                print(json.dumps(server_dict))
                return server_dict

    servers = manager.get_servers()
    for server in servers:
        server_name = server.hostname.split(".")[0]
        if (
            (return_non_fqdn_names and search_item == server_name)
            or server.hostname == search_item
            or server.uuid == search_item
        ):
            server.populate()
            server_dict = namespace_fields(server)
            print(json.dumps(server_dict))
            return server_dict

    print(json.dumps({}))
    return {}


def read_cli_args():
    """Handle command line arguments"""
    parser = argparse.ArgumentParser(
        description="Produce an Ansible Inventory from UpCloud's API"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all active servers as Ansible inventory (default: True)",
    )
    parser.add_argument(
        "--host",
        action="store",
        help="Get all Ansible inventory variables about a specific server",
    )
    parser.add_argument(
        "--return-ip-addresses",
        action="store_true",
        help="Return IP-addresses instead of hostnames with --list. Also configurable in upcloud.ini",
    )

    args = parser.parse_args()

    # Make --list default
    if not args.host:
        args.list = True

    return args


def read_api_credentials(config):
    """Reads API credentials from upcloud.ini or from ENV variables (UPCLOUD_API_USER, UPCLOUD_API_PASSWD)"""

    # Try ENV first
    username = os.getenv("UPCLOUD_API_USER")
    password = os.getenv("UPCLOUD_API_PASSWD")

    if not (username and password):
        if config.has_option("upcloud", "UPCLOUD_API_USER") and config.has_option(
            "upcloud", "UPCLOUD_API_PASSWD"
        ):
            username = config.get("upcloud", "UPCLOUD_API_USER")
            password = config.get("upcloud", "UPCLOUD_API_PASSWD")

    if not (username and password):
        err_msg = "Please set UPCLOUD_API_USER and UPCLOUD_API_PASSWD as environment variables or at upcloud.ini"
        sys.stderr.write(err_msg)
        sys.exit(-1)

    return username, password


def return_error_msg_due_to_faulty_ini_file(missing_variable):
    err_msg = "Could not find {} variable in the ini file. Please check if the ini is configured correctly.".format(
        missing_variable
    )
    sys.stderr.write(err_msg)
    sys.exit(-1)


if __name__ == "__main__":

    # read settings
    args = read_cli_args()

    config = configparser.ConfigParser()
    config.read(os.path.dirname(os.path.realpath(__file__)) + "/upcloud.ini")

    # setup API connection
    username, password = read_api_credentials(config)
    default_timeout = os.getenv("UPCLOUD_API_TIMEOUT") or config.get(
        "upcloud", "default_timeout"
    )
    if not default_timeout:
        default_timeout = None
    else:
        default_timeout = float(default_timeout)
    manager = upcloud_api.CloudManager(username, password, default_timeout)

    # decide whether to return hostnames or ip_addresses
    if config.has_option("upcloud", "return_ip_addresses"):
        with_ip_addresses = (
            str(config.get("upcloud", "return_ip_addresses")).lower() == "true"
        )
    else:
        return_error_msg_due_to_faulty_ini_file("return_ip_addresses")

    if config.has_option("upcloud", "return_non_fqdn_names"):
        return_non_fqdn_names = (
            str(config.get("upcloud", "return_non_fqdn_names")).lower() == "true"
        )
    else:
        return_error_msg_due_to_faulty_ini_file("return_non_fqdn_names")

    if config.has_option("upcloud", "default_ipv_version"):
        default_ipv_version = config.get("upcloud", "default_ipv_version")
    else:
        return_error_msg_due_to_faulty_ini_file("default_ipv_version")

    if args.return_ip_addresses:
        with_ip_addresses = True

    # choose correct action
    if args.list:
        list_servers(
            manager, with_ip_addresses, return_non_fqdn_names, default_ipv_version
        )

    elif args.host:
        get_server(manager, args.host, with_ip_addresses, return_non_fqdn_names)
