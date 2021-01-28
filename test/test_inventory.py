from itertools import product
from inventory.upcloud import list_servers, get_server

class TestInventory(object):
    def test_list_servers(self, manager):
        IPvs_to_test = ['IPv4', 'IPv6']
        possible_configs = list(product([True, False], repeat=2))

        for IP_v in IPvs_to_test:
            for config in possible_configs:
                list_servers(manager, config[0], config[1], IP_v)

    def test_get_server(self, manager):
        possible_configs = list(product([True, False], repeat=3))
        for config in possible_configs:
            get_server(manager, config[0], config[1], config[2])
