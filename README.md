# upcloud-ansible
Dynamic inventory and modules for managing servers via UpCloud's API

The inventory script and modules contain documentation and examples as per
[Ansible's developer guidelines](http://docs.ansible.com/developing_modules.html).
There is an [open PR](https://github.com/ansible/ansible/pull/11586) for the inventory script to be included
within Ansible and the plan is to open a PR for the modules to
[ansible-modules-extra](https://github.com/ansible/ansible-modules-extras)

**Dependencies and supported versions**

* `upcloud-api` 3.0.1 must be installed, `pip install upcloud-api` or get the sources from
  [Github](https://github.com/UpCloudLtd/upcloud-python-api)
* python 2.6 and 2.7 are supported by `upcloud-api`
* tested with ansible 1.9 (and devel)

Note for OS X users:
* install ansible with homebrew can make it hard to know what Python ansible is using, using `pip install ansible` is recommended

## Inventory script

**Installation**

* move to any location you wish, point to the script with `ansible -i /path/to/script/upcloud.py`
* note that upcloud.ini and upcloud.py must be in the same folder; see .ini for settings
* you may wish to use `return_ip_addresses = True` in .ini to ensure that SSH works (hostnames may not be in DNS)
* information on configuring the inventory without specifying `-i` every time:
[http://stackoverflow.com/questions/21958727/where-to-store-ansible-host-file-on-osx](http://stackoverflow.com/questions/21958727/where-to-store-ansible-host-file-on-osx)

**Usage**

```
# match all servers
ansible all -m ping -i /path/to/upcloud.py

# match all servers from upcloud inventory script
ansible uc-all -m ping -i /path/to/upcloud.py

# inventory group servers by upcloud Tags
ansible <any-upcloud-tag> -m <module> -i <path-to-upcloud-inventory>
```

## UpCloud modules

**Installation**

* move the modules to a location of your choice
* make sure to add the location of your choice into library path:
    * [ansible.cfg](http://docs.ansible.com/intro_configuration.html#library)
    * [environment variable or CLI option](http://docs.ansible.com/developing_modules.html)

**Usage**

See the source files for documentation and examples. You may also want to refer to
[UpCloud's API documentation](https://www.upcloud.com/api/)

The following example shows off some of the features of `upcloud`, `upcloud_tag` and `upcloud_firewall` modules:

```yaml

---
- hosts: localhost
  connection: local
  serial: 1
  gather_facts: no

  tasks:
    - name: Create upcloud server
      upcloud:
        state: present
        hostname: web1.example.com
        title: web1.example.com
        zone: uk-lon1
        plan: 1xCPU-1GB
        storage_devices:
            - { size: 30, os: Ubuntu 14.04 }
            - { size: 100 }
      register: upcloud_server # upcloud_server.server will contain the API response body

    # upcloud_server.public_ip shortcut will contain a public IPv4 (preferred) or IPv6 address
    - name: remove new server from known_hosts in case of IP collision
      known_hosts:
        state: absent
        host: "{{ upcloud_server.public_ip }}"

    # small wait to make sure created server is online (might not be instantly after API response)
    - pause: seconds=5

    # upcloud_server.server.password and upcloud_server.server.username
    # can be used to drop in an SSH key. e.g. with https://gist.github.com/elnygren/965a6db4f3fd8e242e90
    - name: Place ssh key on the server
      shell: >
        ./rsync_ssh_key.sh ~/.ssh/id_rsa.pub
        root@{{upcloud_server.public_ip}}:/root/.ssh/authorized_keys
        {{upcloud_server.server.password}}

    - name: tag the created server
      upcloud_tag:
        state: present
        uuid: "{{ upcloud_server.server.uuid }}"
        tags: [ webservers, london ]

    - name: configure firewall
      upcloud_firewall:
        state: present
        uuid: "{{ upcloud_server.server.uuid }}"
        firewall_rules:
        - direction: in
          family: IPv4
          protocol: udp
          destination_port_start: 53
          destination_port_end: 53
          action: accept

        - direction: in
          family: IPv4
          protocol: tcp
          destination_port_start: 22 
          destination_port_end: 22 
          action: accept

        - direction: in
          family: IPv4
          protocol: tcp
          destination_port_start: 80
          destination_port_end: 80
          action: accept

        - direction: in
          family: IPv4
          protocol: tcp
          destination_port_start: 443
          destination_port_end: 443
          action: accept

        # default rule last:
        - direction: in
          action: reject
```


