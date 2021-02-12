class TestFirewall(object):
    def test_match_firewall_rules(self, firewall_manager):
        firewall_rules = firewall_manager.manager.get_firewall_rules()
        firewall_rule_dict_list = [
            fr for fr in firewall_manager.manager.read_json_data('firewall')
            .get('firewall_rules').get('firewall_rule')
        ]
        matched_rule_count = 1
        assert len(firewall_rules) > 0 and len(firewall_rule_dict_list) > 0
        for rule in firewall_rule_dict_list:
            assert firewall_manager.match_firewall_rules(rule, firewall_rules) \
                == (True, str(matched_rule_count))
            matched_rule_count += 1
