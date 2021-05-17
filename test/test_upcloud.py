from itertools import product


class TestUpcloud(object):
    def test_find_server(self, server_manager):
        server_uuid = "008c365d-d307-4501-8efc-cd6d3bb0e494"
        server_hostname = "fi.example.com"
        possible_configs = list(product([server_uuid, server_hostname, None], repeat=2))
        assert len(possible_configs) == 9

        for config in possible_configs:
            found_by_uuid = config[0] == server_uuid
            found_by_hostname = config[1] == server_hostname
            server_should_exist = found_by_uuid or found_by_hostname
            server = server_manager.find_server(config[0], config[1])

            if server_should_exist:
                assert server.uuid == server_uuid or server.hostname == server_hostname
            else:
                assert server is None

    def test_create_server(self, server_manager):
        server_dict = {
            "core_number": "2",
            "memory_amount": "1024",
            "hostname": "my.example.com",
            "zone": "us-chi1",
            "storage_devices": [
                {"os": "01000000-0000-4000-8000-000030200200", "size": 10}
            ],
            "vnc_password": "my-passwd",
            "password_delivery": "email",
            "avoid_host": "12345678",
            "user_data": "https://my.script.com/some_script.py",
            "ip_addresses": [
                {"family": " IPv4", "access": "public"},
                {"family": " IPv6", "access": "public"},
            ],
        }
        server = server_manager.manager.create_server(server_dict)

        assert type(server).__name__ == "Server"
        assert server.core_number == "2"
        assert server.memory_amount == "1024"
        assert type(server.storage_devices[0]).__name__ == "Storage"
        assert type(server.ip_addresses[0]).__name__ == "IPAddress"
