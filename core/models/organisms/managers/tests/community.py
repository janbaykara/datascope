from __future__ import unicode_literals

from django.test import TestCase

from core.utils.helpers import format_datetime
from core.tests.mocks.community import CommunityMock


class TestCommunityManager(TestCase):

    fixtures = ["test-community"]

    def test_get_latest_by_signature(self):
        # Static config with an illegal key
        constant_config = {
            "setting1": "const",
            "illegal": "please"
        }
        signature = CommunityMock.get_signature_from_input("test", **constant_config)
        community = CommunityMock.objects.get_latest_by_signature(signature, **constant_config)
        self.assertIsInstance(community, CommunityMock)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertEqual(community.config.setting1, "const")
        self.assertFalse(hasattr(community.config, "illegal"))
        # Variable config
        variable_config = {
            "$setting2": "variable"
        }
        signature = CommunityMock.get_signature_from_input("test", **variable_config)
        community = CommunityMock.objects.get_latest_by_signature(signature, **variable_config)
        self.assertIsInstance(community, CommunityMock)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertTrue(hasattr(community.config, "$setting2"))
        # Non existant config
        non_existant = {
            "setting1": "variable",
        }
        signature = CommunityMock.get_signature_from_input("test", **non_existant)
        try:
            CommunityMock.objects.get_latest_by_signature(signature, **non_existant)
            self.fail("CommunityManager.get_latest_by_signature did not raise with non-existant community")
        except CommunityMock.DoesNotExist:
            pass
        # Multiple instances with signature
        variable_config = {
            "$setting2": "variable"
        }
        signature = CommunityMock.get_signature_from_input("test-multiple", **variable_config)
        community = CommunityMock.objects.get_latest_by_signature(signature, **variable_config)
        self.assertIsInstance(community, CommunityMock)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertTrue(hasattr(community.config, "$setting2"))
        self.assertEqual(format_datetime(community.created_at), "20150605161754000000")

    def test_get_latest_or_create_by_signature(self):
        # Static config with an illegal key
        constant_config = {
            "setting1": "const",
            "illegal": "please"
        }
        signature = CommunityMock.get_signature_from_input("test", **constant_config)
        community, created = CommunityMock.objects.get_latest_or_create_by_signature(signature, **constant_config)
        self.assertIsInstance(community, CommunityMock)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertFalse(created)
        self.assertEqual(community.config.setting1, "const")
        self.assertFalse(hasattr(community.config, "illegal"))
        # Variable config
        variable_config = {
            "$setting2": "variable"
        }
        signature = CommunityMock.get_signature_from_input("test", **variable_config)
        community, created = CommunityMock.objects.get_latest_or_create_by_signature(signature, **variable_config)
        self.assertIsInstance(community, CommunityMock)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertFalse(created)
        self.assertTrue(hasattr(community.config, "$setting2"))
        # Non existant config
        non_existant = {
            "setting1": "created",
        }
        signature = CommunityMock.get_signature_from_input("test", **non_existant)
        community, created = CommunityMock.objects.get_latest_or_create_by_signature(signature, **non_existant)
        self.assertIsInstance(community, CommunityMock)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertTrue(created)
        self.assertEqual(community.config.setting1, "created")
        # Multiple instances with signature
        variable_config = {
            "$setting2": "variable"
        }
        signature = CommunityMock.get_signature_from_input("test-multiple", **variable_config)
        community, created = CommunityMock.objects.get_latest_or_create_by_signature(signature, **variable_config)
        self.assertIsInstance(community, CommunityMock)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertFalse(created)
        self.assertTrue(hasattr(community.config, "$setting2"))
        self.assertEqual(format_datetime(community.created_at), "20150605161754000000")

    def test_create_by_signature(self):
        # Non existant config
        non_existant = {
            "setting1": "created",
        }
        signature = CommunityMock.get_signature_from_input("test", **non_existant)
        community = CommunityMock.objects.create_by_signature(signature, **non_existant)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertEqual(community.config.setting1, "created")
        # Static config should create duplicate
        constant_config = {
            "setting1": "const",
        }
        signature = CommunityMock.get_signature_from_input("test", **constant_config)
        community = CommunityMock.objects.create_by_signature(signature, **constant_config)
        self.assertIsNotNone(community)
        self.assertIsNotNone(community.id)
        self.assertEqual(community.config.setting1, "const")
        self.assertEqual(CommunityMock.objects.filter(signature=signature).count(), 2)

    def test_delete_manifestations_by_signature(self):
        self.skipTest("not tested")
