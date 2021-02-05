class TestTag(object):
    def test_create_missing_tags(self, tag_manager):
        tag = tag_manager.create_missing_tags(['test'])[0]
        assert type(tag).__name__ == 'Tag'
        assert tag.name == 'test'

    def test_determine_server_uuid_by_hostname(self, tag_manager):
        uuid = tag_manager.determine_server_uuid_by_hostname('fi.example.com')
        assert uuid == '008c365d-d307-4501-8efc-cd6d3bb0e494'

    def test_determine_server_uuid_by_ip(self, tag_manager):
        uuid = tag_manager.determine_server_uuid_by_ip('10.1.0.101')
        assert uuid == '008c365d-d307-4501-8efc-cd6d3bb0e494'

    def test_get_host_tags(self, tag_manager):
        tags = tag_manager.get_host_tags('008c365d-d307-4501-8efc-cd6d3bb0e494')
        assert len(tags) == 1
        assert tags[0] == 'web1'
