#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

import os
from upcloud_api.errors import UpCloudAPIError
from ansible.module_utils.basic import AnsibleModule
from distutils.version import LooseVersion

DOCUMENTATION = """
---

module: upcloud_tag
short_description: Add/remove firewall rules to/from UpCloud servers
description:
    - Add/remove firewall rules to/from UpCloud servers
author: "Elias Nygren (@elnygren)"
options:
    state:
        description: Desired state of the tags.
        default: 'present'
        choices: ['present', 'absent']
    api_user:
        description:
        - UpCloud API username. Can be set as environment variable.
    api_passwd:
        description:
        - UpCloud API password. Can be set as environment variable.
    hostname:
        description:
        - Hostname of the target server to be (un)tagged. Hostname, IP-address or uuid is needed.
    ip_address:
        description:
        - IP address of the target server to be (un)tagged. Hostname, IP-address or uuid is needed.
    uuid:
        description:
        - UUID of the target server to be (un)tagged. Hostname, IP-address or uuid is needed.
    firewall_rules:
        description:
        - List of firewall rules (strings)
notes:
    - UPCLOUD_API_USER and UPCLOUD_API_PASSWD environment variables may be used instead of api_user and api_passwd
    - Better description of UpCloud's API available at U(www.upcloud.com/api/)
requirements:
  - "python >= 2.6"
  - "upcloud-api >= 0.3.4"
"""

EXAMPLES = """

# Make sure that the firewall rules below are present.
# If any given field does not match an existing host rule,
# a new rule will be created.

- name: configure firewall
  upcloud_firewall:
    state: present
    hostname: www13.example.com
    firewall_rules:
      - direction: in,
        family: IPv4,
        protocol: tcp,
        source_address_start: 192.168.1.1,
        source_address_end: 192.168.1.255,
        destination_port_start: 22,
        destination_port_end: 22,
        action: reject

      - direction: in,
        family: IPv4,
        protocol: tcp,
        source_address_start: 192.168.1.1,
        source_address_end: 192.168.1.255,
        destination_port_start: 21,
        destination_port_end: 21,
        action: reject

# Make sure that the firewall rule below is not present.
# If all given fields match a host rule, that rule will be deleted.

- name: open port 22
  upcloud_firewall:
    state: absent
    hostname: www13.example.com
    firewall_rules:
      - direction: in,
        family: IPv4,
        protocol: tcp,
        source_address_start: 192.168.1.1,
        source_address_end: 192.168.1.255,
        destination_port_start: 21,
        destination_port_end: 21,
        action: reject

# Rules may also be deleted by matching just one field,
# such as position. Note that the API will always reorder
# rules so that they start from 1.

- name: delete the first firewall rule
  upcloud_firewall:
    state: absent
    hostname: www13.example.com
    firewall_rules:
      - position: 1

# It is also possible to delete several firewall rules by matching
# with one (or few) fields only:

- name: delete all incoming rules
  upcloud_firewall:
    state: absent
    hostname: www13.example.com
    firewall_rules:
      - direction: in
"""


# make sure that upcloud-api is installed
HAS_UPCLOUD = True
try:
    import upcloud_api

except ImportError:
    HAS_UPCLOUD = False


class FirewallManager:
    """Helpers for managing upcloud_api.FirewallRule (and upcloud_api.Server) instance"""

    def __init__(self, username, password, module):
        self.manager = upcloud_api.CloudManager(username, password)
        self.module = module

    def determine_server_uuid_by_hostname(self, hostname):
        """
        Return uuid based on hostname.
        Fail if there are duplicates of the given hostname.
        """
        servers = self.manager.get_servers()

        found_servers = []
        for server in servers:
            if server.hostname == hostname:
                found_servers.append(server)

        if len(found_servers) > 1:
            self.module.fail_json(
                msg="More than one server matched the given hostname. Please use unique hostnames."
            )

        if len(found_servers) == 1:
            return found_servers[0].uuid
        else:
            self.module.fail_json(msg="No server was found with hostname: " + hostname)

    def determine_server_uuid_by_ip(self, ip_address):
        """
        Return uuid based on IP-address.
        Fail if Upcloud doesn't know the IP-address
        """
        try:
            machine = self.manager.get_server_by_ip(ip_address)
            return machine.uuid
        except UpCloudAPIError as e:
            if e.error_code == "IP_ADDRESS_NOT_FOUND":
                self.module.fail_json(
                    msg="No server was found with IP-address: " + ip_address
                )
            else:
                raise

    def match_firewall_rules(self, given_rule, host_rules):
        """
        Checks given_rule against every host_rule.
        False if no matches were found, True if a match was found.
        """

        def match_firewall_rule(given_rule, host_rule):
            """Match given_rule against one host_rule"""
            for field in given_rule:
                if str(given_rule[field]) != str(getattr(host_rule, field)):
                    return False
            return True

        # Theoretically O(n^2) worst case, but in practice it is much closer to O(n)
        for host_rule in host_rules:
            if match_firewall_rule(given_rule, host_rule):
                return True, host_rule.position

        return False, -1


def run(module, firewall_manager):
    """
    Act based on desired state and given tags.
    - present:
        create any given rule that doesn't match existing rules
    - absent:
        delete any given rule that matches an existing one
    """

    state = module.params["state"]
    firewall_rules = module.params["firewall_rules"]
    uuid = module.params.get("uuid")
    hostname = module.params.get("hostname")
    ip_address = module.params.get("ip_address")

    changed = False

    if not uuid:
        if hostname:
            uuid = firewall_manager.determine_server_uuid_by_hostname(hostname)
        elif ip_address:
            uuid = firewall_manager.determine_server_uuid_by_ip(ip_address)

    host_rules = firewall_manager.manager.get_firewall_rules(uuid)

    # match every rule against host_rules
    if state == "present":
        for rule in firewall_rules:
            matched, position = firewall_manager.match_firewall_rules(rule, host_rules)

            # create any given rule that didn't match existing rules
            if not matched:
                firewall_manager.manager.create_firewall_rule(uuid, rule)
                changed = True

    # delete any given rule that matches an existing one
    if state == "absent":
        for rule in firewall_rules:

            # each given rule can match multiple times
            while True:
                matched, position = firewall_manager.match_firewall_rules(
                    rule, host_rules
                )
                if matched:
                    firewall_manager.manager.delete_firewall_rule(uuid, position)
                    changed = True

                    # update host_rules from API to get new positions
                    host_rules = firewall_manager.manager.get_firewall_rules(uuid)
                else:
                    break

    module.exit_json(changed=changed)


def main():
    """main execution path"""
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(choices=["present", "absent"], default="present"),
            api_user=dict(aliases=["UPCLOUD_API_USER"], no_log=True),
            api_passwd=dict(aliases=["UPCLOUD_API_PASSWD"], no_log=True),
            hostname=dict(type="str"),
            ip_address=dict(type="str"),
            uuid=dict(aliases=["id"], type="str"),
            firewall_rules=dict(type="list", required=True),
        ),
        required_one_of=(["uuid", "hostname", "ip_address"],),
    )

    # ensure dependencies and API credentials are in place
    #

    if not HAS_UPCLOUD:
        module.fail_json(
            msg="upcloud-api required for this module (`pip install upcloud-api`)"
        )

    api_user = module.params.get("api_user") or os.getenv("UPCLOUD_API_USER")
    api_passwd = module.params.get("api_passwd") or os.getenv("UPCLOUD_API_PASSWD")

    if not api_user or not api_passwd:
        module.fail_json(
            msg="""Please set UPCLOUD_API_USER and UPCLOUD_API_PASSWD environment variables or provide api_user and api_passwd arguments."""
        )

    # begin execution. Catch all unhandled exceptions.
    # Note: UpCloud's API has good error messages that the api client passes on.
    #

    firewall_manager = FirewallManager(api_user, api_passwd, module)
    try:
        run(module, firewall_manager)
    except Exception as e:
        import traceback

        module.fail_json(msg=str(e) + str(traceback.format_exc()))


# the required module boilerplate
#


if __name__ == "__main__":
    main()
