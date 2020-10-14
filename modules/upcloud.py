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

module: upcloud
short_description: Create/delete a server in UpCloud
description:
    - Create/delete a server in UpCloud or ensure that an existing server is started
author: "Elias Nygren (@elnygren)"
options:
    state:
        description:
        - Desired state of the target
        default: present
        choices: ['present', 'absent']
    api_user:
        description:
        - UpCloud API username. Can be set as environment variable.
    api_passwd:
        description:
        - UpCloud API password. Can be set as environment variable.
    title:
        description:
        - String. Server's title in UpCloud. Optional if state is absent.
    hostname:
        description:
        - String. Server's hostname in UpCloud. Hostname or UUID needed for targeting an existing server. Optional if state is absent.
    zone:
        description:
        - String. Server's zone in UpCloud. Optional if state is absent.
    storage_devices:
        description:
        - Array of storage dicts. Server's storages in UpCloud. Optional if state is absent.
    uuid:
        description:
        - Optional string. Server's UUID. UUID or hostname needed for targeting an existing server.
    plan:
        description:
        - Optional string. Server's plan if using UpCloud preconfigured instances.
    core_number:
        description:
        - Optional integer. Server's CPU cores if using UpCloud freely scalable instances.
    memory_amount:
        description:
        - Optional integer. Server's RAM if using UpCloud freely scalable instances.
    ip_addresses:
        description:
        - Optional array of IP-address dicts. Server's IP-addresses in UpCloud. UpCloud assigns 1 public and 1 private IPv4 by default.
    firewall:
        description:
        - Bool. Firewall on/off in UpCloud.
        default: no
        choices: [ "yes", "no" ]
    vnc:
        description:
        - Bool. VNC on/off in UpCloud.
        default: no
        choices: [ "yes", "no" ]
    vnc_password:
        description:
        - Optional string. VNC password in UpCloud.
    video_model:
        description:
        - Optional string. Video adapter in UpCloud.
    timezone:
        description:
        - Optional string. Timezone in UpCloud.
    password_delivery:
        description:
        - Optional string. Password delivery method. UpCloud Ansible module grabs SSH credentials from API response.
        - UpCloud's API client defaults to 'none' (as opposed to 'email' or 'sms')
    nic_model:
        description:
        - Optional string. Network adapter in UpCloud.
    boot_order:
        description:
        - Optional string. Boot order in UpCloud.
    avoid_host:
        description:
        - Optional string or integer. Host ID in UpCloud.
    user:
        description:
        - Optional string. Linux user that should be created with given ssh_keys.
        - When user and ssh_keys are being used, no password is delivered in API response.
        - UpCloud's API defaults to 'root' user
    ssh_keys:
        description:
        - Optional list of strings. SSH keys that should be added to the given user.
        - When user and ssh_keys are being used, no password is delivered in API response.
notes:
    - UPCLOUD_API_USER and UPCLOUD_API_PASSWD environment variables may be used instead of api_user and api_passwd
    - Better description of UpCloud's API available at U(www.upcloud.com/api/)
requirements:
  - "python >= 2.6"
  - "upcloud-api >= 0.3.4"
'''

EXAMPLES = '''

# Create and destroy a server.
# Step 1: If www1.example.com exists, ensure it is started. If it doesn't exist, create it.
# Step 2: Stop and destroy the server created in step 1.

- name: Create upcloud server
  upcloud:
    state: present
    hostname: www1.example.com
    title: www1.example.com
    zone: uk-lon1
    plan: 1xCPU-1GB
    storage_devices:
        - { size: 30, os: Ubuntu 14.04 }
        - { size: 100 }
    user: upclouduser
    ssh_keys:
        - ssh-rsa AAAAB3NzaC1yc2EAA[...]ptshi44x user@some.host
        - ssh-dss AAAAB3NzaC1kc3MAA[...]VHRzAA== someuser@some.other.host
  register: upcloud_server

- debug: msg="upcloud_server => {{ upcloud_server }}"

- name: Wait for SSH to come up
    wait_for: host={{ upcloud_server.public_ip }} port=22 delay=5 timeout=320 state=started

# tip: hostname can also be used to destroy a server
- name: Destroy upcloud server
  upcloud:
    state: absent
    uuid: "{{ upcloud_server.server.uuid }}"

'''

from distutils.version import LooseVersion
import os

# make sure that upcloud-api is installed
HAS_UPCLOUD = True
try:
    import upcloud_api
    from upcloud_api import CloudManager

    if LooseVersion(upcloud_api.__version__) < LooseVersion('0.3.4'):
        HAS_UPCLOUD = False

except ImportError, e:
    HAS_UPCLOUD = False


class ServerManager():
    """Helpers for managing upcloud.Server instance"""

    def __init__(self, api_user, api_passwd, default_timeout):
        self.manager = CloudManager(api_user, api_passwd, default_timeout)


    def find_server(self, uuid, hostname):
        """
        Finds a server first by uuid (if given) and then by hostname.

        Exits if the given hostname has duplicates as this could potentially
        lead to destroying the wrong server.
        """
        # try with uuid first, if given
        if uuid:
            try:
                server = self.manager.get_server(uuid)
                return server
            except Exception, e:
                pass # no server found

        # try with hostname, if given and nothing was found with uuid
        if hostname:
            servers = self.manager.get_servers()

            found_servers = []
            for server in servers:
                if server.hostname == hostname:
                    found_servers.append(server)

            if len(found_servers) > 1:
                module.fail_json(msg='More than one server matched the given hostname. Please use unique hostnames.')

            if len(found_servers) == 1:
                return found_servers[0]

        return None


    def create_server(self, module):
        """Create a server from module.params. Filters out unwanted attributes."""

        # filter out 'filter_keys' and those who equal None from items to get server's attributes for POST request
        items = module.params.items()
        filter_keys = set(['state', 'api_user', 'api_passwd', 'user', 'ssh_keys'])
        server_dict = dict((key,value) for key, value in items if key not in filter_keys and value is not None)

        if module.params.get('ssh_keys'):
            login_user = upcloud_api.login_user_block(
                username=module.params.get('user'),
                ssh_keys=module.params['ssh_keys'],
                create_password=False
            )
            server_dict['login_user'] = login_user

        return self.manager.create_server(server_dict)


def run(module, server_manager):
    """create/destroy/start server based on its current state and desired state"""

    state = module.params['state']
    uuid = module.params.get('uuid')
    hostname = module.params.get('hostname')

    changed = True

    if state == 'present':
        server = server_manager.find_server(uuid, hostname)

        if not server:
            # create server, if one was not found
            server = server_manager.create_server(module)
        else:
            if server.state=='started':
                changed = False

        server.ensure_started()

        module.exit_json(changed=changed, server=server.to_dict(), public_ip=server.get_public_ip())

    elif state == 'absent':
        server = server_manager.find_server(uuid, hostname)

        if server:
            server.stop_and_destroy()
            module.exit_json(changed=True, msg="destroyed" + server.hostname)

        module.exit_json(changed=False, msg="server absent (didn't exist in the first place)")


def main():
    """main execution path"""

    module = AnsibleModule(
        argument_spec = dict(
            state = dict(choices=['present', 'absent'], default='present'),
            api_user = dict(aliases=['CLIENT_ID'], no_log=True),
            api_passwd = dict(aliases=['API_KEY'], no_log=True),

            # required for creation
            title = dict(type='str'),
            hostname = dict(type='str'),
            zone = dict(type='str'),
            storage_devices = dict(type='list'),

            # required for destroying
            uuid = dict(aliases=['id'], type='str', default=None),

            # optional, but useful
            plan = dict(type='str'),
            core_number = dict(type='int'),
            memory_amount = dict(type='int'),
            ip_addresses = dict(type='list'),
            firewall = dict(type='bool'),
            ssh_keys = dict(type='list'),
            user = dict(type='str'),

            # optional, nice-to-have
            vnc = dict(type='bool'),
            vnc_password = dict(type='str'),
            video_model = dict(type='str'),
            timezone = dict(type='str'),
            password_delivery = dict(type='str'),
            nic_model = dict(type='str'),
            boot_order = dict(type='str'),
            avoid_host = dict(type='str')
        ),
        required_together = (
            ['core_number', 'memory_amount'],
            ['api_user', 'api_passwd']
        ),
        mutually_exclusive = (
            ['plan', 'core_number'],
            ['plan', 'memory_amount']
        ),
        required_one_of = (
            ['uuid', 'hostname'],
        ),
    )


    # ensure dependencies and API credentials are in place
    #

    if not HAS_UPCLOUD:
        module.fail_json(msg='upcloud-api required for this module (`pip install upcloud-api`)')

    api_user = module.params.get('api_user') or os.getenv('UPCLOUD_API_USER')
    api_passwd = module.params.get('api_passwd') or os.getenv('UPCLOUD_API_PASSWD')
    default_timeout = os.getenv('UPCLOUD_API_TIMEOUT')

    if not default_timeout:
        default_timeout = None
    else:
        default_timeout = float(default_timeout)

    if not api_user or not api_passwd:
        module.fail_json(msg='''Please set UPCLOUD_API_USER and UPCLOUD_API_PASSWD environment variables or provide api_user and api_passwd arguments.''')

    # begin execution. Catch all unhandled exceptions.
    # Note: UpCloud's API has good error messages that the api client passes on.

    server_manager = ServerManager(api_user, api_passwd, default_timeout)
    try:
        run(module, server_manager)
    except Exception as e:
        import traceback
        module.fail_json(msg=str(e) + str(traceback.format_exc()))


# the required module boilerplate
#

from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
