from itertools import product
from inventory.upcloud import list_servers, get_server


class TestInventory(object):
    def test_list_servers(self, manager):
        IPvs_to_test = ["IPv4", "IPv6"]
        possible_configs = list(product([True, False], repeat=2))

        assert (len(possible_configs)) == 4

        for IP_v in IPvs_to_test:
            for config in possible_configs:
                servers = list_servers(manager, config[0], config[1], IP_v)
                if IP_v == "IPv4" and config[0] and config[1]:
                    assert servers.get("uc_all") == ["10.1.0.101"]
                    assert servers.get("web1") == ["10.1.0.101"]
                    assert servers.get("fi_hel1") == ["10.1.0.101"]

    def test_get_server(self, manager):
        search_items = ["008c365d-d307-4501-8efc-cd6d3bb0e494"]
        possible_configs = list(product([True, False], repeat=2))

        assert (len(possible_configs)) == 4

        for search_item in search_items:
            for config in possible_configs:
                server = get_server(manager, search_item, config[0], config[1])
                assert server.get("uc_uuid") == "008c365d-d307-4501-8efc-cd6d3bb0e494"
