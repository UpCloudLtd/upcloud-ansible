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

DOCUMENTATION = '''
---

module: upcloud_tag
short_description: Add/remove tags to/from UpCloud servers
description:
    - Create new tags and add them to, or remove them, from UpCloud servers
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
    tags:
        description:
        - List of tags (strings)
notes:
    - This module will create missing tags (tags have to be created before assigning), but will not remove tags
      as this could lead into tags being removed from other than the target server.
    - UPCLOUD_API_USER and UPCLOUD_API_PASSWD environment variables may be used instead of api_user and api_passwd
    - Better description of UpCloud's API available at U(www.upcloud.com/api/)
requirements:
  - "python >= 2.6"
  - "upcloud-api >= 0.3.4"
'''

EXAMPLES = '''

# Adding and removing tags.
# Any tags not existing in API /tags will be created if need be.
# Notice that either server.uuid or server.hostname can be used.
# uuid is slightly faster due to GET /server/uuid.

- name: add tags
  upcloud_tag:
    state: present
    hostname: web1.example.com
    tags: ['test1', 'test2']

- name: remove tags
  upcloud_tag:
    state: absent
    uuid: xxxxxxxx-xxxx-Mxxx-Nxxx-xxxxxxxxxxxx
    tags: ['test1', 'test2']

'''

from distutils.version import LooseVersion
from upcloud_api.errors import UpCloudClientError, UpCloudAPIError

import os

# make sure that upcloud-api is installed
HAS_UPCLOUD = True
try:
    import upcloud_api
    from upcloud_api import CloudManager

    if LooseVersion(upcloud_api.__version__) < LooseVersion('0.3.1'):
        HAS_UPCLOUD = False

except ImportError, e:
    HAS_UPCLOUD = False


class TagManager():
    """Helpers for managing upcloud_api.Tag (and upcloud_api.Server) instance"""

    def __init__(self, username, password, module):
        self.manager = upcloud_api.CloudManager(username, password)
        self.module = module


    def create_missing_tags(self, given_tags):
        """
        Create any tags that are present in given_tags but missing from UpCloud.
        """

        upcloud_tags = self.manager.get_tags()
        upcloud_tags = [ str(uc_tag) for uc_tag in upcloud_tags ]

        for given_tag in given_tags:
            if given_tag not in upcloud_tags:
                self.manager.create_tag(given_tag)

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
            self.module.fail_json(msg='More than one server matched the given hostname. Please use unique hostnames.')

        if len(found_servers) == 1:
            return found_servers[0].uuid
        else:
            self.module.fail_json(msg='No server was found with hostname: ' + hostname)

    def determine_server_uuid_by_ip(self, ip_address):
        """
        Return uuid based on IP-address.
        Fail if Upcloud doesn't know the IP-address
        """
        try:
            machine = self.manager.get_server_by_ip(ip_address)
            return machine.uuid
        except UpCloudAPIError as e:
            if e.error_code == 'IP_ADDRESS_NOT_FOUND':
                self.module.fail_json(msg='No server was found with IP-address: ' + ip_address)
            else:
                raise

    def get_host_tags(self, uuid):
        host_tags = self.manager.get_server(uuid).tags
        return [ str(host_tag) for host_tag in host_tags ]


def run(module, tag_manager):
    """
    Act based on desired state and given tags.
    - present:
        create any given tags not present in upcloud's available tags
        add any given tags not present to host
    - absent:
        remove any given tags present from the host
        (don't remove them from upcloud's available tags, might be present in other servers)
    """

    state =         module.params['state']
    tags =          module.params['tags']
    uuid =          module.params.get('uuid')
    hostname =      module.params.get('hostname')
    ip_address =    module.params.get('ip_address')

    changed = False

    if not uuid:
        if hostname:
            uuid = firewall_manager.determine_server_uuid_by_hostname(hostname)
        elif ip_address:
            uuid = firewall_manager.determine_server_uuid_by_ip(ip_address)

    # make sure the host has all tags
    if state == 'present':

        # tags must exist in UpCloud before thay can be assigned
        tag_manager.create_missing_tags(tags)

        host_tags = tag_manager.get_host_tags(uuid)

        # tags - host_tags = tags_to_add
        tags_to_add = [ tag for tag in tags if tag not in host_tags ]

        if tags_to_add:
            tag_manager.manager.assign_tags(uuid, tags)
            changed=True

        module.exit_json(changed=changed)

    # makse sure the host has none of the specified tags
    if state == 'absent':

        host_tags = tag_manager.get_host_tags(uuid)

        # intersection of tags and host_tags
        tags_to_remove = [ tag for tag in tags if tag in host_tags ]

        if len(tags_to_remove) > 0:
            changed = True
            tag_manager.manager.remove_tags(uuid, tags_to_remove)

        module.exit_json(changed=changed)


def main():
    """main execution path"""

    module = AnsibleModule(
        argument_spec = dict(
            state = dict(choices=['present', 'absent'], default='present'),
            api_user = dict(aliases=['UPCLOUD_API_USER'], no_log=True),
            api_passwd = dict(aliases=['UPCLOUD_API_PASSWD'], no_log=True),

            hostname = dict(type='str'),
            ip_address = dict(type='str'),
            uuid = dict(aliases=['id'], type='str'),
            tags = dict(type='list', required=True)
        ),
        required_one_of = (
            ['uuid', 'hostname', 'ip_address'],
        )
    )


    # ensure dependencies and API credentials are in place
    #

    if not HAS_UPCLOUD:
        module.fail_json(msg='upcloud-api required for this module (`pip install upcloud-api`)')

    api_user = module.params.get('api_user') or os.getenv('UPCLOUD_API_USER')
    api_passwd = module.params.get('api_passwd') or os.getenv('UPCLOUD_API_PASSWD')

    if not api_user or not api_passwd:
        module.fail_json(msg='''Please set UPCLOUD_API_USER and UPCLOUD_API_PASSWD environment variables or provide api_user and api_passwd arguments.''')


    # begin execution. Catch all unhandled exceptions.
    # Note: UpCloud's API has good error messages that the api client passes on.
    #

    tag_manager = TagManager(api_user, api_passwd, module)
    try:
        run(module, tag_manager)
    except Exception as e:
        import traceback
        module.fail_json(msg=str(e) + str(traceback.format_exc()))


# the required module boilerplate
#

from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
