import os
import json
import pytest
from upcloud_api import Server, IPAddress, Storage, Tag, FirewallRule
from modules.upcloud_tag import TagManager
from modules.upcloud_firewall import FirewallManager
from modules.upcloud import ServerManager


class MockedManager:
    def get_servers(self, populate=False):
        servers = (
            self.read_json_data("server").get("servers").get("server")
            if populate
            else self.read_json_data("server_populated").get("servers").get("server")
        )
        server_list = list()
        for server in servers:
            server_list.append(Server(server, cloud_manager=self))
        return server_list

    def get_server(self, uuid):
        servers = self.get_servers()
        for server in servers:
            if server.uuid == uuid:
                return server
        raise Exception("Server with uuid: {} does not exist in test data".format(uuid))

    def create_server(self, server):
        return Server._create_server_obj(server, cloud_manager=self)

    def get_server_by_ip(self, ip_address):
        servers = self.get_servers()
        IPs = self.get_ips()
        for ip in IPs:
            if ip.address == ip_address:
                for server in servers:
                    if server.uuid == ip.server:
                        return server

    def get_server_data(self, uuid):
        server_data = {}
        servers = self.read_json_data("server_populated").get("servers").get("server")
        for server in servers:
            if server.get("uuid") == uuid:
                server_data = server
        IPAddresses = IPAddress._create_ip_address_objs(
            server.pop("ip_addresses"), cloud_manager=self
        )

        storages = Storage._create_storage_objs(
            server.pop("storage_devices"), cloud_manager=self
        )
        return server_data, IPAddresses, storages

    def get_ips(self, ignore_ips_without_server=False):
        data = self.read_json_data("ip_address")
        IPs = IPAddress._create_ip_address_objs(
            data.get("ip_addresses"), self, ignore_ips_without_server
        )
        return IPs

    def get_tags(self):
        data = self.read_json_data("tag")
        return [Tag(cloud_manager=self, **tag) for tag in data["tags"]["tag"]]

    def create_tag(self, name, description=None, servers=[]):
        tag = {"name": name}
        if description:
            tag["description"] = description
        if servers:
            tag["servers"] = servers
        return Tag(cloud_manager=self, **tag)

    def get_firewall_rules(self):
        data = self.read_json_data("firewall")
        return [
            FirewallRule(**firewall_rule)
            for firewall_rule in data["firewall_rules"]["firewall_rule"]
        ]

    def read_json_data(self, filename):
        cwd = os.path.dirname(__file__)
        with open("{}/json_data/{}.json".format(cwd, filename), "r") as json_file:
            data = json.load(json_file)
        return data


class MockedServerManager(ServerManager):
    def __init__(self, manager):
        self.manager = manager


class MockedTagManager(TagManager):
    def __init__(self, manager):
        self.manager = manager


class MockedFirewallManager(FirewallManager):
    def __init__(self, manager):
        self.manager = manager


@pytest.fixture(scope="module")
def manager():
    return MockedManager()


@pytest.fixture(scope="module")
def server_manager():
    manager = MockedManager()
    return MockedServerManager(manager)


@pytest.fixture(scope="module")
def tag_manager():
    manager = MockedManager()
    return MockedTagManager(manager)


@pytest.fixture(scope="module")
def firewall_manager():
    manager = MockedManager()
    return MockedFirewallManager(manager)
