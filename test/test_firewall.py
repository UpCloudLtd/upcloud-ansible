from itertools import product

class TestFirewall(object):
    def test_match_firewall_rules(self, firewall_manager):
        firewall_rules = firewall_manager.manager.get_firewall_rules()
        assert len(firewall_rules) > 0
        for rule in firewall_rules:
            firewall_manager.match_firewall_rules(rule, firewall_rules)
